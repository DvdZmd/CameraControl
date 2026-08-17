function updateOperationalStatusSummary() {
    const indicator = document.getElementById('operational-status-indicator');
    const label = document.getElementById('operational-status-label');
    if (!indicator || !label) return;

    const cards = Array.from(document.querySelectorAll('.home-health-card:not(.state-disabled)'));
    let state = 'ok';
    let text = 'Operativo';
    if (cards.some(card => card.classList.contains('state-error'))) {
        state = 'error';
        text = 'Atención requerida';
    } else if (cards.some(card => card.classList.contains('state-pending'))) {
        state = 'pending';
        text = 'Consultando';
    } else if (cards.some(card => card.classList.contains('state-warning'))) {
        state = 'warning';
        text = 'Revisar estado';
    }

    indicator.classList.remove('state-pending', 'state-ok', 'state-warning', 'state-error');
    indicator.classList.add(`state-${state}`);
    label.textContent = text;
}

function setHomeHealthState(cardId, detailId, state, detail) {
    const card = document.getElementById(cardId);
    const detailElement = document.getElementById(detailId);
    if (!card || !detailElement) return;

    card.classList.remove('state-pending', 'state-ok', 'state-warning', 'state-error');
    card.classList.add(`state-${state}`);
    detailElement.textContent = detail;
    updateOperationalStatusSummary();
}

function markHomeStatusUpdated() {
    const updated = document.getElementById('home-status-updated');
    if (!updated) return;
    updated.textContent = `Actualizado ${new Date().toLocaleTimeString()}`;
}

async function refreshHomeCapabilities() {
    try {
        const response = await fetch('/api/system/capabilities');
        const data = await response.json();
        if (!response.ok) throw new Error('No se pudieron consultar las capacidades');

        const profile = document.getElementById('home-profile-name');
        const instance = document.getElementById('home-instance-name');
        const apiVersion = document.getElementById('home-api-version');
        if (profile) profile.textContent = data.profile || '--';
        if (instance) instance.textContent = data.instance || '--';
        if (apiVersion) apiVersion.textContent = data.api_version || '--';
        return data;
    } catch (error) {
        const apiVersion = document.getElementById('home-api-version');
        if (apiVersion) apiVersion.textContent = 'N/D';
        return null;
    }
}

function renderHomeCameraHealth(data, error = null) {
    if (error || !data || data.available === false) {
        setHomeHealthState(
            'home-camera-health',
            'home-camera-health-detail',
            'error',
            error?.message || data?.message || data?.error || 'No disponible'
        );
        return;
    }

    const resolution = data.current_width && data.current_height
        ? `${data.current_width}×${data.current_height}`
        : null;
    const parts = [data.camera_model, resolution].filter(Boolean);
    parts.push(data.stream_enabled ? 'stream activo' : 'stream apagado');
    setHomeHealthState(
        'home-camera-health',
        'home-camera-health-detail',
        data.stream_enabled ? 'ok' : 'warning',
        parts.join(' · ')
    );
}

function renderHomeEsp32Health(data, error = null) {
    if (error || !data) {
        setHomeHealthState(
            'home-esp32-health', 'home-esp32-health-detail', 'error',
            error?.message || 'No se pudo consultar BLE'
        );
        return;
    }
    const connected = Boolean(data.connected);
    const identity = data.device_name || data.address || 'Sin dispositivo conectado';
    setHomeHealthState(
        'home-esp32-health', 'home-esp32-health-detail',
        connected ? 'ok' : 'warning', identity
    );
}

function renderHomeSystemHealth(data) {
    const freePercent = Number(data?.storage?.free_percent);
    const temperature = Number(data?.cpu_temperature_c);
    const hasData = Number.isFinite(freePercent) || Number.isFinite(temperature) || Boolean(data?.power);
    let state = hasData ? 'ok' : 'warning';
    let detail = hasData ? 'Sin alertas' : 'Información parcial no disponible';

    if (data?.power?.undervoltage_now || (Number.isFinite(freePercent) && freePercent <= 10)) {
        state = 'error';
        detail = data?.power?.undervoltage_now ? 'Bajo voltaje actual' : 'Almacenamiento crítico';
    } else if (
        data?.power?.undervoltage_occurred
        || (Number.isFinite(freePercent) && freePercent <= 20)
        || (Number.isFinite(temperature) && temperature >= 75)
    ) {
        state = 'warning';
        detail = data?.power?.undervoltage_occurred
            ? 'Se detectó bajo voltaje previamente'
            : (Number.isFinite(freePercent) && freePercent <= 20 ? 'Poco almacenamiento libre' : 'Temperatura elevada');
    }
    setHomeHealthState('home-system-health', 'home-system-health-detail', state, detail);
}

async function refreshOperationalDashboard() {
    const button = document.getElementById('home-refresh-status-btn');
    const spinner = button?.querySelector('.btn-spinner');
    if (button) button.disabled = true;
    if (spinner) spinner.classList.remove('hidden');

    const features = (window.CAMERA_CONTROL && window.CAMERA_CONTROL.features) || {};
    const operations = [refreshHomeCapabilities(), refreshRaspberryStatus()];
    if (features.camera) {
        operations.push(
            fetchCameraStatus()
                .then(data => renderHomeCameraHealth(data))
                .catch(error => renderHomeCameraHealth(null, error))
        );
    }
    if (features.esp32) operations.push(refreshEsp32Status());

    try {
        await Promise.allSettled(operations);
        markHomeStatusUpdated();
    } finally {
        if (button) button.disabled = false;
        if (spinner) spinner.classList.add('hidden');
    }
}
