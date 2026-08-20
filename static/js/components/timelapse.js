let timelapseRunning = false;
let timelapseCapturesPage = 1;

function timelapseIntervalSeconds() {
    const value = parseInt(document.getElementById('tl-interval').value, 10);
    const unit = document.getElementById('tl-interval-unit').value;
    return unit === 'minutes' ? value * 60 : value;
}

function syncTimelapseIntervalMinimum() {
    const input = document.getElementById('tl-interval');
    const unit = document.getElementById('tl-interval-unit').value;
    const lightEnabled = document.getElementById('tl-light-enabled').checked;
    const warmupSeconds = Number(document.getElementById('tl-light-warmup').value) || 0;
    const minimum = unit === 'seconds' ? Math.max(2, lightEnabled ? warmupSeconds : 0) : 1;
    input.min = String(minimum);
    if (Number(input.value) < minimum) input.value = String(minimum);
}

function setTimelapseControlsDisabled(disabled) {
    ['tl-interval', 'tl-interval-unit', 'tl-w', 'tl-h', 'tl-auto-resume',
        'tl-light-enabled', 'tl-light-intensity', 'tl-folder-name',
        'tl-light-warmup', 'tl-resolution-preset', 'tl-save-sensor-readings',
        'tl-capture-overlay'].forEach(id => {
        const element = document.getElementById(id);
        if (element) element.disabled = disabled;
    });
    const saveButton = document.querySelector('[data-action="save-timelapse-config"]');
    if (saveButton) saveButton.disabled = disabled;
}

function renderTimelapseStatus(data) {
    timelapseRunning = Boolean(data.running);
    const button = document.getElementById('btn-timelapse');
    const feedback = document.getElementById('timelapse-status');
    if (button) {
        button.textContent = timelapseRunning ? 'Detener Timelapse' : 'Iniciar Timelapse';
        button.classList.toggle('btn-danger', timelapseRunning);
    }
    setTimelapseControlsDisabled(timelapseRunning);

    if (feedback) {
        feedback.classList.remove('hidden', 'status-error');
        if (data.last_error) {
            feedback.textContent = data.last_error;
            feedback.classList.add('status-error');
        } else if (timelapseRunning) {
            feedback.textContent = `Capturando cada ${data.interval_seconds} segundos a ${data.width}x${data.height}`;
        } else if (data.desired_running) {
            feedback.textContent = 'Pendiente de reanudación automática cuando la cámara esté disponible';
        } else {
            feedback.textContent = 'Timelapse detenido';
        }
    }

    document.getElementById('tl-desired-state').textContent = data.desired_running ? 'Activo' : 'Detenido';
    document.getElementById('tl-capture-count').textContent = data.capture_count ?? 0;
    document.getElementById('tl-last-capture').textContent = data.last_capture_at
        ? new Date(data.last_capture_at).toLocaleString()
        : '--';
    document.getElementById('tl-save-path').textContent = data.save_path || '--';
}

function hydrateTimelapseConfig(data) {
    const features = (window.CAMERA_CONTROL && window.CAMERA_CONTROL.features) || {};
    const seconds = Number(data.interval_seconds || 10);
    const useMinutes = seconds >= 60 && seconds % 60 === 0;
    document.getElementById('tl-interval-unit').value = useMinutes ? 'minutes' : 'seconds';
    document.getElementById('tl-interval').value = useMinutes ? seconds / 60 : seconds;
    document.getElementById('tl-w').value = data.width;
    document.getElementById('tl-h').value = data.height;
    const resolution = `${data.width}x${data.height}`;
    const preset = document.getElementById('tl-resolution-preset');
    const hasPreset = Array.from(preset.options).some(option => option.value === resolution);
    preset.value = hasPreset ? resolution : 'custom';
    document.getElementById('tl-custom-resolution').style.display = hasPreset ? 'none' : 'flex';
    document.getElementById('tl-auto-resume').checked = Boolean(data.auto_resume);
    document.getElementById('tl-capture-overlay').checked = Boolean(data.capture_overlay_enabled);
    document.getElementById('tl-save-sensor-readings').checked = Boolean(
        features.sensors && data.save_sensor_readings
    );
    document.getElementById('tl-light-enabled').checked = Boolean(
        features.lighting && data.light_enabled
    );
    document.getElementById('tl-light-intensity').value = data.light_intensity || 100;
    document.getElementById('tl-light-intensity-value').textContent = `${data.light_intensity || 100}%`;
    document.getElementById('tl-light-warmup').value = data.light_warmup_seconds ?? 3;
    document.getElementById('tl-folder-name').value = data.folder_name || 'default';
    syncTimelapseIntervalMinimum();
}

async function refreshTimelapseStatus({ hydrate = false } = {}) {
    try {
        const response = await fetch('/api/timelapse/status');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo consultar el timelapse');
        if (hydrate) hydrateTimelapseConfig(data);
        renderTimelapseStatus(data);
        return data;
    } catch (error) {
        const feedback = document.getElementById('timelapse-status');
        if (feedback) {
            feedback.classList.remove('hidden');
            feedback.classList.add('status-error');
            feedback.textContent = error.message;
        }
        return null;
    }
}

async function saveTimelapseConfig() {
    const intervalSeconds = timelapseIntervalSeconds();
    const lightEnabled = document.getElementById('tl-light-enabled').checked;
    const lightWarmupSeconds = Number(document.getElementById('tl-light-warmup').value);
    if (!Number.isInteger(lightWarmupSeconds) || lightWarmupSeconds < 0 || lightWarmupSeconds > 60) {
        throw new Error('La espera de luz debe ser un entero entre 0 y 60 segundos');
    }
    if (lightEnabled && intervalSeconds < lightWarmupSeconds) {
        throw new Error(`Con luz activa el intervalo mínimo es de ${lightWarmupSeconds} segundos`);
    }
    const payload = {
        interval_seconds: intervalSeconds,
        width: parseInt(document.getElementById('tl-w').value, 10),
        height: parseInt(document.getElementById('tl-h').value, 10),
        auto_resume: document.getElementById('tl-auto-resume').checked,
        save_sensor_readings: document.getElementById('tl-save-sensor-readings').checked,
        capture_overlay_enabled: document.getElementById('tl-capture-overlay').checked,
        light_enabled: lightEnabled,
        light_intensity: parseInt(document.getElementById('tl-light-intensity').value, 10),
        light_warmup_seconds: lightWarmupSeconds,
        folder_name: document.getElementById('tl-folder-name').value.trim()
    };
    const response = await fetch('/api/timelapse/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo guardar la configuración');
    renderTimelapseStatus(data);
    await loadTimelapseFolders(data.folder_name);
    return data;
}

function formatFileSize(sizeBytes) {
    const bytes = Number(sizeBytes) || 0;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function selectedTimelapseFolder() {
    return document.getElementById('tl-folder-select').value;
}

async function loadTimelapseFolders(preferredFolder = null) {
    const response = await fetch('/api/timelapse/folders');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudieron consultar las carpetas');
    const select = document.getElementById('tl-folder-select');
    const selected = preferredFolder || select.value || data.selected;
    select.replaceChildren();
    data.folders.forEach(folder => {
        const option = document.createElement('option');
        option.value = folder;
        option.textContent = folder;
        select.appendChild(option);
    });
    if (data.folders.includes(selected)) select.value = selected;
    if (select.value) await loadTimelapseCaptures(1);
}

function timelapseCaptureUrl(capturePath) {
    const params = new URLSearchParams({
        folder: selectedTimelapseFolder(),
        path: capturePath
    });
    return `/api/timelapse/capture/preview?${params}`;
}

function renderTimelapseCapturesPagination(data) {
    const pagination = document.getElementById('tl-captures-pagination');
    pagination.replaceChildren();
    if (data.pages <= 1) return;

    const previous = document.createElement('button');
    previous.type = 'button';
    previous.textContent = 'Anterior';
    previous.disabled = data.page <= 1;
    previous.addEventListener('click', () => loadTimelapseCaptures(data.page - 1));

    const label = document.createElement('span');
    label.textContent = `Página ${data.page} de ${data.pages}`;

    const next = document.createElement('button');
    next.type = 'button';
    next.textContent = 'Siguiente';
    next.disabled = data.page >= data.pages;
    next.addEventListener('click', () => loadTimelapseCaptures(data.page + 1));
    pagination.append(previous, label, next);
}

async function loadTimelapseCaptures(page = 1) {
    const folder = selectedTimelapseFolder();
    const body = document.getElementById('tl-captures-body');
    const feedback = document.getElementById('tl-captures-feedback');
    if (!folder) {
        body.replaceChildren();
        document.getElementById('tl-captures-pagination').replaceChildren();
        document.getElementById('tl-select-all-captures').checked = false;
        feedback.classList.remove('hidden', 'status-error');
        feedback.textContent = 'No hay directorios de timelapse';
        return;
    }
    try {
        const params = new URLSearchParams({ folder, page: String(page), per_page: '20' });
        const response = await fetch(`/api/timelapse/captures?${params}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudieron consultar las capturas');
        body.replaceChildren();
        document.getElementById('tl-select-all-captures').checked = false;
        data.captures.forEach(capture => {
            const row = document.createElement('tr');
            const selectorCell = document.createElement('td');
            const selector = document.createElement('input');
            selector.type = 'checkbox';
            selector.className = 'tl-capture-selector';
            selector.value = capture.path;
            selectorCell.appendChild(selector);
            const previewCell = document.createElement('td');
            const previewLink = document.createElement('a');
            previewLink.href = timelapseCaptureUrl(capture.path);
            previewLink.target = '_blank';
            previewLink.rel = 'noopener';
            const preview = document.createElement('img');
            preview.className = 'timelapse-capture-preview';
            preview.src = previewLink.href;
            preview.alt = `Preview de ${capture.name}`;
            preview.loading = 'lazy';
            preview.decoding = 'async';
            previewLink.appendChild(preview);
            previewCell.appendChild(previewLink);
            const values = [
                capture.name,
                capture.path,
                formatFileSize(capture.size_bytes),
                new Date(capture.modified_at).toLocaleString()
            ];
            row.appendChild(selectorCell);
            row.appendChild(previewCell);
            values.forEach(value => {
                const cell = document.createElement('td');
                cell.textContent = value;
                row.appendChild(cell);
            });
            const actionCell = document.createElement('td');
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn-secondary';
            button.dataset.action = 'download-timelapse-capture';
            button.dataset.capturePath = capture.path;
            button.textContent = 'Descargar';
            actionCell.appendChild(button);
            row.appendChild(actionCell);
            body.appendChild(row);
        });
        timelapseCapturesPage = data.page;
        renderTimelapseCapturesPagination(data);
        feedback.classList.remove('hidden', 'status-error');
        feedback.textContent = `${data.total} capturas en ${folder}`;
    } catch (error) {
        feedback.classList.remove('hidden');
        feedback.classList.add('status-error');
        feedback.textContent = error.message;
    }
}

function downloadTimelapseCapture(capturePath) {
    const params = new URLSearchParams({
        folder: selectedTimelapseFolder(),
        path: capturePath
    });
    window.location.assign(`/api/timelapse/capture/download?${params}`);
}

function downloadTimelapseFolder() {
    const folder = selectedTimelapseFolder();
    if (folder) window.location.assign(`/api/timelapse/folders/${encodeURIComponent(folder)}/download`);
}

async function downloadSelectedCaptures() {
    const captures = Array.from(document.querySelectorAll('.tl-capture-selector:checked'))
        .map(input => input.value);
    const feedback = document.getElementById('tl-captures-feedback');
    if (!captures.length) {
        feedback.classList.remove('hidden');
        feedback.classList.add('status-error');
        feedback.textContent = 'Seleccioná al menos una captura';
        return;
    }
    const folder = selectedTimelapseFolder();
    const response = await fetch('/api/timelapse/captures/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder, captures })
    });
    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'No se pudieron descargar las capturas');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `${folder}-seleccion.zip`;
    link.click();
    URL.revokeObjectURL(url);
}

function selectedCapturePaths() {
    return Array.from(document.querySelectorAll('.tl-capture-selector:checked'))
        .map(input => input.value);
}

async function deleteSelectedCaptures() {
    const captures = selectedCapturePaths();
    if (!captures.length) throw new Error('Seleccioná al menos una captura');
    if (!window.confirm(`¿Borrar definitivamente ${captures.length} capturas?`)) return;
    const response = await fetch('/api/timelapse/captures', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: selectedTimelapseFolder(), captures })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudieron borrar las capturas');
    const targetPage = captures.length === document.querySelectorAll('.tl-capture-selector').length
        ? Math.max(1, timelapseCapturesPage - 1)
        : timelapseCapturesPage;
    await loadTimelapseCaptures(targetPage);
}

async function deleteTimelapseFolder() {
    const folder = selectedTimelapseFolder();
    if (!folder) throw new Error('No hay un directorio seleccionado');
    if (!window.confirm(`¿Borrar definitivamente el directorio "${folder}" y todas sus capturas?`)) return;
    const response = await fetch(`/api/timelapse/folders/${encodeURIComponent(folder)}`, {
        method: 'DELETE'
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo borrar el directorio');
    await loadTimelapseFolders();
}

async function toggleTimelapse() {
    const btn = document.getElementById('btn-timelapse');
    const statusDiv = document.getElementById('timelapse-status');
    if (btn) btn.disabled = true;
    try {
        let endpoint;
        if (timelapseRunning) {
            endpoint = '/api/timelapse/stop';
        } else {
            await saveTimelapseConfig();
            endpoint = '/api/timelapse/start';
        }
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cambiar el timelapse');
        renderTimelapseStatus(data);
    } catch (error) {
        statusDiv.classList.remove('hidden');
        statusDiv.classList.add('status-error');
        statusDiv.textContent = error.message;
        await refreshTimelapseStatus();
    } finally {
        if (btn) btn.disabled = false;
    }
}
