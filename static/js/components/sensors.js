let sensorHistoryPage = 1;

function renderSensorLoggingConfig(data) {
    document.getElementById('sensor-logging-enabled').checked = Boolean(data.enabled);
    document.getElementById('sensor-logging-interval').value = data.interval_seconds;
}

async function loadSensorLoggingConfig() {
    const feedback = document.getElementById('sensor-logging-feedback');
    try {
        const response = await fetch('/api/sensors/logging-config');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo consultar la configuración');
        renderSensorLoggingConfig(data);
    } catch (error) {
        feedback.classList.remove('hidden');
        feedback.classList.add('status-error');
        feedback.textContent = error.message;
    }
}

async function saveSensorLoggingConfig() {
    const feedback = document.getElementById('sensor-logging-feedback');
    const payload = {
        enabled: document.getElementById('sensor-logging-enabled').checked,
        interval_seconds: Number(document.getElementById('sensor-logging-interval').value)
    };
    try {
        const response = await fetch('/api/sensors/logging-config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo guardar la configuración');
        renderSensorLoggingConfig(data);
        feedback.classList.remove('hidden', 'status-error');
        feedback.textContent = data.enabled
            ? `Escritura activada cada ${data.interval_seconds} segundos`
            : 'Escritura en base de datos desactivada';
    } catch (error) {
        feedback.classList.remove('hidden');
        feedback.classList.add('status-error');
        feedback.textContent = error.message;
    }
}

function sensorHistoryParams(page) {
    const params = new URLSearchParams({ page: String(page), per_page: '20' });
    const fields = [
        'start-date', 'end-date',
        'min-temperature-air', 'max-temperature-air',
        'min-humidity-air', 'max-humidity-air',
        'min-temperature-soil', 'max-temperature-soil',
        'min-humidity-soil', 'max-humidity-soil'
    ];
    fields.forEach(field => {
        const value = document.getElementById(`history-${field}`)?.value;
        if (value) params.set(field.replaceAll('-', '_'), value);
    });
    return params;
}

function renderSensorHistory(data) {
    const body = document.getElementById('sensor-history-body');
    const pagination = document.getElementById('sensor-history-pagination');
    if (!body || !pagination) return;

    body.replaceChildren();
    document.getElementById('sensor-select-all-readings').checked = false;
    data.readings.forEach(reading => {
        const row = document.createElement('tr');
        const selectorCell = document.createElement('td');
        const selector = document.createElement('input');
        selector.type = 'checkbox';
        selector.className = 'sensor-reading-selector';
        selector.value = String(reading.id);
        selectorCell.appendChild(selector);
        row.appendChild(selectorCell);
        const values = [
            new Date(reading.timestamp).toLocaleString(),
            `${Number(reading.temperature_air).toFixed(1)} °C`,
            `${Number(reading.humidity_air).toFixed(1)} %`,
            `${Number(reading.temperature_soil).toFixed(1)} °C`,
            `${Number(reading.humidity_soil).toFixed(1)} %`,
            reading.pan_pulse_us == null ? '--' : `${reading.pan_pulse_us} µs`,
            reading.tilt_pulse_us == null ? '--' : `${reading.tilt_pulse_us} µs`,
            reading.timelapse_folder_name || '--'
        ];
        values.forEach(value => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });
        body.appendChild(row);
    });

    pagination.replaceChildren();
    if (data.pages > 1) {
        const previous = document.createElement('button');
        previous.type = 'button';
        previous.textContent = 'Anterior';
        previous.disabled = data.page <= 1;
        previous.addEventListener('click', () => loadSensorHistory(data.page - 1));

        const label = document.createElement('span');
        label.textContent = `Página ${data.page} de ${data.pages}`;

        const next = document.createElement('button');
        next.type = 'button';
        next.textContent = 'Siguiente';
        next.disabled = data.page >= data.pages;
        next.addEventListener('click', () => loadSensorHistory(data.page + 1));
        pagination.append(previous, label, next);
    }
}

async function deleteSelectedSensorReadings() {
    const ids = Array.from(document.querySelectorAll('.sensor-reading-selector:checked'))
        .map(input => Number(input.value));
    if (!ids.length) throw new Error('Seleccioná al menos una lectura');
    if (!window.confirm(`¿Borrar definitivamente ${ids.length} lecturas?`)) return;
    const response = await fetch('/api/sensors/readings', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudieron borrar las lecturas');
    await loadSensorHistory(sensorHistoryPage);
}

async function deleteAllSensorReadings() {
    if (!window.confirm('¿Borrar definitivamente TODAS las lecturas de sensores?')) return;
    const response = await fetch('/api/sensors/readings/all', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudieron borrar las lecturas');
    await loadSensorHistory(1);
}

async function loadSensorHistory(page = 1) {
    const feedback = document.getElementById('sensor-history-feedback');
    try {
        const response = await fetch(`/api/sensors/readings?${sensorHistoryParams(page)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo consultar el historial');
        sensorHistoryPage = data.page;
        renderSensorHistory(data);
        if (feedback) {
            feedback.classList.remove('hidden', 'status-error');
            feedback.textContent = data.total
                ? `${data.total} lecturas encontradas`
                : 'No se encontraron lecturas';
        }
    } catch (error) {
        if (feedback) {
            feedback.classList.remove('hidden');
            feedback.classList.add('status-error');
            feedback.textContent = error.message;
        }
    }
}

