const CAMERA_API_BASE = '/api/camera';

function cameraApiUrl(path) {
    return `${CAMERA_API_BASE}${path}`;
}


function setActiveTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === tabId);
    });
}

function showEsp32Feedback(message, isError = false) {
    const feedback = document.getElementById('esp32-feedback');
    if (!feedback) return;

    feedback.classList.remove('hidden', 'status-error');
    feedback.textContent = message;
    if (isError) {
        feedback.classList.add('status-error');
    }
}

function setEsp32ConnectLoading(isLoading) {
    const button = document.getElementById('esp32-connect-btn');
    const label = document.getElementById('esp32-connect-label');
    const spinner = button ? button.querySelector('.btn-spinner') : null;

    if (button) button.disabled = isLoading;
    if (label) label.textContent = isLoading ? 'Conectando...' : 'Conectar ESP32';
    if (spinner) spinner.classList.toggle('hidden', !isLoading);
}

function stateValue(state, key) {
    if (!state || !Object.prototype.hasOwnProperty.call(state, key)) {
        return null;
    }
    const value = state[key];
    return value === null || value === undefined || value === '' ? null : value;
}

function formatSavedPosition(savedPosition) {
    if (!savedPosition || savedPosition.pan === undefined || savedPosition.tilt === undefined) {
        return '--';
    }
    return `P ${savedPosition.pan} / T ${savedPosition.tilt}`;
}

function normalizeSpeedMode(value) {
    if (value === null || value === undefined || value === '') {
        return null;
    }
    const mode = Number(value);
    return Number.isInteger(mode) && mode >= 0 && mode <= 4 ? String(mode) : null;
}

async function refreshEsp32Status() {
    try {
        const response = await fetch('/api/esp32/status');
        const data = await response.json();

        const badge = document.getElementById('esp32-status-badge');
        const deviceName = document.getElementById('esp32-device-name');
        const address = document.getElementById('esp32-address');
        const lastStateEl = document.getElementById('esp32-last-state');
        const savedPositionEl = document.getElementById('esp32-saved-position');
        const speedSelect = document.getElementById('esp32-speed-select');

        if (badge) {
            badge.textContent = data.connected ? 'Conectado' : 'Desconectado';
            badge.className = `esp32-badge ${data.connected ? 'connected' : 'disconnected'}`;
        }
        
        if (deviceName) deviceName.textContent = data.device_name || '--';
        if (address) address.textContent = data.address || '--';
        
        // Actualizar estado y sensores
        const lastState = data.last_state || {};
        if (lastStateEl) {
            // La clave para velocidad es 'S'
            const speedMode = stateValue(lastState, 'S');
            lastStateEl.textContent = speedMode !== null ? `Perfil Vel. ${speedMode}` : 'N/A';
        }
        if (speedSelect) {
            const savedSpeedMode = normalizeSpeedMode(data.saved_speed_mode);
            const telemetrySpeedMode = normalizeSpeedMode(stateValue(lastState, 'S'));
            const speedMode = savedSpeedMode || telemetrySpeedMode;
            if (speedMode !== null) {
                speedSelect.value = speedMode;
            }
        }

        // Sensores Ambientales y de Suelo
        const dhtTemp = stateValue(lastState, 'DT');
        const dhtHumidity = stateValue(lastState, 'DH');
        const dsTemp = stateValue(lastState, 'DS');
        const soilPercent = stateValue(lastState, 'SP');
        const soilRaw = stateValue(lastState, 'SR');
        document.getElementById('sensor-dht-temp').textContent = dhtTemp !== null ? `${parseFloat(dhtTemp).toFixed(1)} °C` : '--';
        document.getElementById('sensor-dht-humidity').textContent = dhtHumidity !== null ? `${parseFloat(dhtHumidity).toFixed(1)} %` : '--';
        document.getElementById('sensor-ds-temp').textContent = dsTemp !== null ? `${parseFloat(dsTemp).toFixed(1)} °C` : '--';
        document.getElementById('sensor-soil-percent').textContent = soilPercent !== null ? `${soilPercent} %` : '--';
        document.getElementById('sensor-soil-raw').textContent = soilRaw !== null ? soilRaw : '--';

        // Estado de Movimiento (Servos)
        const panPulse = stateValue(lastState, 'P');
        const tiltPulse = stateValue(lastState, 'T');
        document.getElementById('servo-pan-pulse').textContent = panPulse !== null ? panPulse : '--';
        document.getElementById('servo-tilt-pulse').textContent = tiltPulse !== null ? tiltPulse : '--';
        if (savedPositionEl) {
            savedPositionEl.textContent = formatSavedPosition(data.saved_position);
        }

    } catch (error) {
        console.error('Error obteniendo estado ESP32:', error);
    }
}

async function connectEsp32() {
    setEsp32ConnectLoading(true);
    showEsp32Feedback('Conectando con ESP32...');
    try {
        const response = await fetch('/api/esp32/connect', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || data.connected === false) {
            throw new Error(data.error || 'No se pudo conectar al ESP32');
        }
        showEsp32Feedback('ESP32 conectado correctamente');
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo conectar al ESP32', true);
    } finally {
        setEsp32ConnectLoading(false);
    }
}

async function disconnectEsp32() {
    try {
        const response = await fetch('/api/esp32/disconnect', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || data.connected !== false) {
            throw new Error(data.error || 'No se pudo desconectar del ESP32');
        }
        showEsp32Feedback('ESP32 desconectado');
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo desconectar del ESP32', true);
    }
}

async function sendEsp32Move(direction) {
    try {
        const response = await fetch('/api/esp32/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ direction })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo enviar el movimiento');
        }
        showEsp32Feedback(`Movimiento enviado: ${direction}`);
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo enviar el movimiento', true);
    }
}

async function sendEsp32Center() {
    try {
        const response = await fetch('/api/esp32/center', { method: 'POST' });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo centrar el sistema');
        }
        showEsp32Feedback('Comando de centrado enviado');
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo centrar el sistema', true);
    }
}

async function saveEsp32CurrentPosition() {
    try {
        const response = await fetch('/api/esp32/position/current', { method: 'POST' });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo configurar la posición actual');
        }
        const savedPositionEl = document.getElementById('esp32-saved-position');
        if (savedPositionEl) {
            savedPositionEl.textContent = formatSavedPosition(data.saved_position);
        }
        showEsp32Feedback('Posición actual configurada');
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo configurar la posición actual', true);
    }
}

async function returnEsp32ToSavedPosition() {
    try {
        const response = await fetch('/api/esp32/position/return', { method: 'POST' });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo volver a la posición configurada');
        }
        showEsp32Feedback('Volviendo a la posición configurada');
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo volver a la posición configurada', true);
    }
}

async function setEsp32Speed(mode) {
    try {
        const response = await fetch('/api/esp32/speed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: Number(mode) })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo actualizar la velocidad');
        }
        const speedSelect = document.getElementById('esp32-speed-select');
        if (speedSelect) {
            speedSelect.value = String(mode);
        }
        showEsp32Feedback(`Velocidad actualizada al perfil ${mode}`);
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo actualizar la velocidad', true);
    }
}

async function sendEsp32CustomCommand() {
    const input = document.getElementById('esp32-command-input');
    if (!input) return;

    const command = input.value.trim();
    if (!command) {
        showEsp32Feedback('Escribe un comando antes de enviarlo', true);
        return;
    }

    try {
        const response = await fetch('/api/esp32/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo enviar el comando');
        }
        showEsp32Feedback(`Comando enviado: ${command}`);
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo enviar el comando', true);
    }
}

/* --- Funciones para el control de Tuya --- */

function showTuyaFeedback(message, isError = false) {
    const feedback = document.getElementById('tuya-feedback');
    if (!feedback) return;

    feedback.classList.remove('hidden', 'status-error');
    feedback.textContent = message;
    if (isError) {
        feedback.classList.add('status-error');
    }
    // Ocultar el mensaje después de unos segundos
    setTimeout(() => feedback.classList.add('hidden'), 3000);
}

async function refreshTuyaStatus() {
    try {
        const response = await fetch('/api/tuya/devices');
        const data = await response.json();

        const list = document.getElementById('tuya-devices-list');
        if (!list) return;

        if (data.ok && Array.isArray(data.devices)) {
            renderTuyaDevices(data.devices);
        } else {
            list.innerHTML = '<p class="empty-state">No se pudo cargar el estado de Tuya.</p>';
            console.error('Error obteniendo estado de Tuya:', data.error);
        }
    } catch (error) {
        console.error('Error de red obteniendo estado de Tuya:', error);
        const list = document.getElementById('tuya-devices-list');
        if (list) {
            list.innerHTML = '<p class="empty-state">Tuya offline.</p>';
        }
    }
}

function renderTuyaDevices(devices) {
    const list = document.getElementById('tuya-devices-list');
    if (!list) return;

    const editingState = getTuyaNameEditingState(list);

    if (devices.length === 0) {
        list.innerHTML = '<p class="empty-state">Sin dispositivos configurados.</p>';
        return;
    }

    list.innerHTML = devices.map(device => {
        const isOn = device.is_on === true;
        const statusClass = device.status_ok ? (isOn ? 'on' : 'off') : 'unknown';
        const statusText = device.status_ok ? (isOn ? 'Encendido' : 'Apagado') : 'Error';
        const checked = isOn ? 'checked' : '';
        const disabled = device.status_ok ? '' : 'disabled';
        const tuyaName = device.tuya_name
            ? `<span>Tuya: ${escapeHtml(device.tuya_name)}</span>`
            : '<span>Tuya: sin nombre remoto</span>';
        const editedName = editingState.names.get(String(device.id));
        const displayName = editedName !== undefined ? editedName : device.name;
        const telemetry = renderTuyaTelemetry(device);
        const settings = renderTuyaSettings(device);
        const error = device.status_ok ? '' : `<p class="tuya-error">${escapeHtml(device.error || 'No se pudo consultar Tuya')}</p>`;
        return `
            <div class="tuya-device-card">
                <div class="tuya-device-info">
                    <div class="tuya-device-title">
                        <input
                            class="tuya-name-input"
                            type="text"
                            value="${escapeAttribute(displayName)}"
                            data-tuya-name-input="${device.id}"
                            data-tuya-original-name="${escapeAttribute(device.name)}"
                            aria-label="Nombre informativo"
                        >
                        <button type="button" data-action="save-tuya-device-name" data-device-id="${device.id}">Guardar</button>
                    </div>
                    ${tuyaName}
                    <span>${escapeHtml(device.device_id)}</span>
                    <small>${escapeHtml(device.switch_code)}</small>
                </div>
                ${error}
                ${telemetry}
                ${settings}
                <div class="tuya-controls">
                    <span class="device-badge ${statusClass}">${statusText}</span>
                    <div class="toggle-switch">
                        <input
                            type="checkbox"
                            class="toggle-checkbox"
                            id="tuya-toggle-${device.id}"
                            data-action="toggle-tuya-device"
                            data-device-id="${device.id}"
                            ${checked}
                            ${disabled}
                        >
                        <label for="tuya-toggle-${device.id}" class="toggle-label"></label>
                    </div>
                    <button type="button" data-action="refresh-tuya-device-details" data-device-id="${device.id}">Refrescar Tuya</button>
                </div>
            </div>
        `;
    }).join('');

    restoreTuyaNameFocus(editingState);
}

function renderTuyaTelemetry(device) {
    const electrical = device.electrical || {};
    const safety = device.safety || {};
    const capabilities = device.capabilities || {};
    const faults = Array.isArray(safety.faults) ? safety.faults : [];
    const faultText = faults.length
        ? faults.map(fault => fault.label || fault.code).join(', ')
        : 'Sin fallas';
    const faultClass = faults.length ? 'warning' : 'ok';

    if (!device.status_ok) {
        return '';
    }

    const meteringGrid = capabilities.has_electrical_metering ? `
        <div class="tuya-metrics-grid">
            ${renderTuyaMetric(
                'Voltaje',
                formatMeasurement(electrical.voltage_v, 'V', 1),
                'Tension de red medida por el enchufe en su entrada/salida de alimentacion. Sirve para ver si la linea esta cerca del valor esperado.'
            )}
            ${renderTuyaMetric(
                'Corriente',
                formatMeasurement(electrical.current_ma, 'mA', 0),
                'Corriente instantanea que esta demandando la carga conectada al enchufe. No es acumulativa.'
            )}
            ${renderTuyaMetric(
                'Potencia',
                formatMeasurement(electrical.power_w, 'W', 1),
                'Potencia instantanea calculada por el medidor interno del enchufe a partir de la carga conectada.'
            )}
            ${renderTuyaMetric(
                'Energia',
                formatMeasurement(electrical.added_energy_kwh, 'kWh', 3),
                'Energia incremental reportada por Tuya. Para historico o acumulado confiable CameraControl debe guardar muestras en la base de datos.'
            )}
        </div>
    ` : '<p class="tuya-muted">Sin medición eléctrica reportada.</p>';

    return `
        <div class="tuya-telemetry">
            ${meteringGrid}
            <div class="tuya-status-line">
                <span class="tuya-fault ${faultClass}">${escapeHtml(faultText)}</span>
                <span>${device.cached ? 'cache' : 'vivo'}${device.fetched_at ? ` · ${escapeHtml(formatTuyaTimestamp(device.fetched_at))}` : ''}</span>
            </div>
        </div>
    `;
}

function renderTuyaMetric(label, value, hint) {
    return `
        <div class="tuya-metric">
            <span class="tuya-metric-label">
                ${escapeHtml(label)}
                <span
                    class="tuya-hint"
                    title="${escapeAttribute(hint)}"
                    aria-label="${escapeAttribute(hint)}"
                    tabindex="0"
                >!</span>
            </span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `;
}

function renderTuyaSettings(device) {
    if (!device.status_ok) return '';

    const settings = device.settings || {};
    const safety = device.safety || {};
    const items = [
        ['Countdown', formatCountdown(settings.countdown_seconds)],
        ['Relay inicio', humanizeTuyaRelayStatus(settings.relay_status)],
        ['LED', humanizeTuyaLightMode(settings.light_mode)],
        ['Bloqueo', formatBooleanState(safety.child_lock)],
    ].filter(([, value]) => value !== '--');

    if (!items.length) return '';

    return `
        <div class="tuya-settings-list">
            ${items.map(([label, value]) => `
                <span><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}</span>
            `).join('')}
        </div>
    `;
}

function formatMeasurement(value, unit, decimals) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return '--';
    }
    return `${value.toFixed(decimals)} ${unit}`;
}

function formatCountdown(value) {
    if (!Number.isInteger(value)) return '--';
    if (value <= 0) return 'Inactivo';
    const minutes = Math.floor(value / 60);
    const seconds = value % 60;
    if (minutes <= 0) return `${seconds}s`;
    return `${minutes}m ${seconds}s`;
}

function formatBooleanState(value) {
    if (value === true) return 'Activo';
    if (value === false) return 'Inactivo';
    return '--';
}

function humanizeTuyaRelayStatus(value) {
    return {
        power_on: 'Encender',
        power_off: 'Apagar',
        last: 'Último estado',
        on: 'Encender',
        off: 'Apagar',
        memory: 'Memoria',
    }[value] || (value ? String(value) : '--');
}

function humanizeTuyaLightMode(value) {
    return {
        none: 'Apagado',
        relay: 'Sigue relay',
        pos: 'Ubicación',
    }[value] || (value ? String(value) : '--');
}

function formatTuyaTimestamp(timestamp) {
    const date = new Date(Number(timestamp) * 1000);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function escapeAttribute(value) {
    return escapeHtml(value);
}

function getTuyaNameEditingState(list) {
    const activeInput = document.activeElement && document.activeElement.matches('.tuya-name-input')
        ? document.activeElement
        : null;
    const names = new Map();

    list.querySelectorAll('.tuya-name-input').forEach(input => {
        const deviceId = input.dataset.tuyaNameInput;
        if (!deviceId) return;

        const originalName = input.dataset.tuyaOriginalName || '';
        if (input === activeInput || input.value !== originalName) {
            names.set(deviceId, input.value);
        }
    });

    return {
        activeDeviceId: activeInput ? activeInput.dataset.tuyaNameInput : null,
        selectionStart: activeInput ? activeInput.selectionStart : null,
        selectionEnd: activeInput ? activeInput.selectionEnd : null,
        names,
    };
}

function restoreTuyaNameFocus(editingState) {
    if (!editingState.activeDeviceId) return;

    const input = document.querySelector(`[data-tuya-name-input="${editingState.activeDeviceId}"]`);
    if (!input) return;

    input.focus();
    if (editingState.selectionStart !== null && editingState.selectionEnd !== null) {
        input.setSelectionRange(editingState.selectionStart, editingState.selectionEnd);
    }
}

async function toggleTuyaPlug(event) {
    const toggle = event.target;
    const newState = toggle.checked;
    const deviceId = toggle.dataset.deviceId;

    if (!deviceId) return;

    try {
        const response = await fetch(`/api/tuya/devices/${deviceId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ on: newState })
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'La operación falló');
        }
        showTuyaFeedback(`Dispositivo ${newState ? 'encendido' : 'apagado'}.`);
        await refreshTuyaStatus(); // Refrescar estado para confirmar
    } catch (error) {
        showTuyaFeedback(error.message, true);
        toggle.checked = !newState; // Revertir el cambio visual si hay error
    }
}

async function saveTuyaDeviceName(deviceId) {
    const input = document.querySelector(`[data-tuya-name-input="${deviceId}"]`);
    if (!input) return;

    const name = input.value.trim();
    if (!name) {
        showTuyaFeedback('El nombre informativo no puede quedar vacío.', true);
        return;
    }

    try {
        const response = await fetch(`/api/tuya/devices/${deviceId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'No se pudo actualizar el nombre.');
        }

        showTuyaFeedback('Nombre informativo actualizado.');
        await refreshTuyaStatus();
    } catch (error) {
        showTuyaFeedback(error.message || 'No se pudo actualizar el nombre.', true);
    }
}

async function refreshTuyaDeviceDetails(deviceId) {
    try {
        const response = await fetch(`/api/tuya/devices/${deviceId}/details`, { method: 'POST' });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'No se pudo refrescar el nombre de Tuya.');
        }

        showTuyaFeedback('Nombre de Tuya actualizado.');
        await refreshTuyaStatus();
    } catch (error) {
        showTuyaFeedback(error.message || 'No se pudo refrescar el nombre de Tuya.', true);
    }
}

async function addTuyaDevice() {
    const nameInput = document.getElementById('tuya-device-name');
    const deviceIdInput = document.getElementById('tuya-device-id');
    const switchCodeInput = document.getElementById('tuya-switch-code');

    if (!nameInput || !deviceIdInput || !switchCodeInput) return;

    const payload = {
        name: nameInput.value.trim(),
        device_id: deviceIdInput.value.trim(),
        switch_code: switchCodeInput.value.trim() || 'switch_1'
    };

    if (!payload.name || !payload.device_id) {
        showTuyaFeedback('Nombre y Device ID son requeridos.', true);
        return;
    }

    try {
        const response = await fetch('/api/tuya/devices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'No se pudo agregar el dispositivo.');
        }

        nameInput.value = '';
        deviceIdInput.value = '';
        switchCodeInput.value = 'switch_1';
        showTuyaFeedback('Dispositivo agregado.');
        await refreshTuyaStatus();
    } catch (error) {
        showTuyaFeedback(error.message || 'No se pudo agregar el dispositivo.', true);
    }
}

let cameraMaxW = 1280;
let cameraMaxH = 720;

async function initCameraSpecs() {
    const res = await fetch(cameraApiUrl('/camera_status'));
    const data = await res.json();
    
    cameraMaxW = data.max_width;
    cameraMaxH = data.max_height;
    
    // Mostramos al usuario el límite real de su cámara
    document.getElementById('max-res-hint').innerText = 
        `Límite del sensor: ${cameraMaxW} x ${cameraMaxH}`;
        
    // Si la cámara es una V3, el límite será aprox 4608x2592
    // Si es una V2, será 3280x2464
}

function setControlValue(control, value) {
    const element = document.getElementById(control);
    if (!element || value === undefined || value === null) return;

    element.value = String(value);

    const display = document.getElementById(`val-${control}`);
    if (display) {
        display.innerText = element.value;
    }
}

function setResolutionValue(width, height) {
    const label = document.getElementById('resolution-label');
    if (label && width && height) {
        label.innerText = `${width}x${height} @ 30fps`;
    }

    const preset = document.getElementById('res-preset');
    const customInputs = document.getElementById('custom-res-inputs');
    if (!preset || !width || !height) return;

    const resolution = `${width}x${height}`;
    const presetOption = Array.from(preset.options).find(option => option.value === resolution);
    if (presetOption) {
        preset.value = resolution;
        if (customInputs) customInputs.style.display = 'none';
    } else {
        preset.value = 'custom';
        if (customInputs) customInputs.style.display = 'flex';
        const customW = document.getElementById('custom-w');
        const customH = document.getElementById('custom-h');
        if (customW) customW.value = width;
        if (customH) customH.value = height;
    }
}

function hydrateCameraControls(status) {
    setResolutionValue(status.current_width, status.current_height);
    applyVideoRotation(parseInt(status.display_rotation || 0, 10));

    const controls = status.controls || {};
    Object.entries(controls).forEach(([control, value]) => setControlValue(control, value));

    const afMode = document.getElementById('AfMode');
    const focusSlider = document.getElementById('manual-focus-container');
    if (afMode && focusSlider) {
        focusSlider.style.display = afMode.value === "0" ? "block" : "none";
    }
}

function handleResolutionChange(val) {
    const customDiv = document.getElementById('custom-res-inputs');
    if (val === 'custom') {
        customDiv.style.display = 'flex';
    } else {
        customDiv.style.display = 'none';
        const [w, h] = val.split('x');
        updateCameraSettings({ width: parseInt(w), height: parseInt(h) });
    }
}

function restoreControlPanelState() {
    const panel = document.querySelector('.controls-panel');
    const toggleBtn = document.getElementById('toggle-panel-btn');
    const hidden = localStorage.getItem('controlsPanelHidden') === 'true';

    if (hidden) {
        panel.classList.add('hidden');
        if (toggleBtn) toggleBtn.textContent = 'Mostrar panel';
    } else {
        panel.classList.remove('hidden');
        if (toggleBtn) toggleBtn.textContent = 'Ocultar panel';
    }
}

function toggleControlPanel() {
    const panel = document.querySelector('.controls-panel');
    const toggleBtn = document.getElementById('toggle-panel-btn');
    const hidden = panel.classList.toggle('hidden');

    if (toggleBtn) toggleBtn.textContent = hidden ? 'Mostrar panel' : 'Ocultar panel';
    localStorage.setItem('controlsPanelHidden', hidden);
}

function applyCustomResolution() {
    let w = parseInt(document.getElementById('custom-w').value);
    let h = parseInt(document.getElementById('custom-h').value);
    
    // Validación de límites
    if (w > cameraMaxW) w = cameraMaxW;
    if (h > cameraMaxH) h = cameraMaxH;
    
    if (w > 0 && h > 0) {
        updateCameraSettings({ width: w, height: h });
    }
}

async function captureCustomPhoto() {
    const w = document.getElementById('photo-w').value;
    const h = document.getElementById('photo-h').value;
    const video = document.getElementById('video-feed');
    
    // Indicador visual de que el stream se pausa para capturar
    video.style.opacity = "0.3";
    
    try {
        // Construimos la URL con los parámetros custom
        const response = await fetch(cameraApiUrl(`/take_photo_custom?w=${w}&h=${h}`));
        if (!response.ok) throw new Error("Error en la captura");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Photo_${w}x${h}_${Date.now()}.jpg`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error(err);
    } finally {
        // Restauramos la opacidad y forzamos al navegador a reconectar el stream MJPEG
        video.style.opacity = "1";
        setTimeout(() => {
            const currentSrc = video.src.split('?')[0];
            video.src = currentSrc + '?t=' + new Date().getTime();
        }, 1000); // Damos un segundo para que la cámara termine de re-inicializarse
    }
}


// Función para manejar la visibilidad de los controles según el hardware
async function checkCameraCapabilities() {
    try {
        const res = await fetch(cameraApiUrl('/camera_status'));
        const status = await res.json();
        
        const afContainer = document.getElementById('af-container');
        const focusSlider = document.getElementById('manual-focus-container');
        
        if (!status.af_supported) {
            if (afContainer) afContainer.style.display = 'none';
            if (focusSlider) focusSlider.style.display = 'none';
        } else {
            // Si soporta AF, escuchamos cambios en el modo para mostrar el slider manual
            const afModeSelect = document.getElementById('AfMode');
            afModeSelect.addEventListener('change', (e) => {
                // 0 es el valor para Manual en camera_utils
                focusSlider.style.display = e.target.value == "0" ? "block" : "none";
            });
        }
    } catch (e) {
        console.error("Error verificando capacidades:", e);
    }
}

// Aplicar un preset desde el selector
async function applyPreset(presetName) {
    if (!presetName) return;
    
    try {
        const response = await fetch(cameraApiUrl('/apply_preset'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: presetName })
        });
        
        if (response.ok) {
            // Recargar la página para actualizar los valores de los sliders
            location.reload(); 
        }
    } catch (err) {
        console.error("Error al aplicar preset:", err);
    }
}

// Resetear la cámara
async function resetCamera() {
    try {
        const response = await fetch(cameraApiUrl('/reset'), { method: 'POST' });
        if (response.ok) {
            location.reload();
        }
    } catch (err) {
        console.error("Error al resetear cámara:", err);
    }
}

async function triggerSoftwareUpdate() {
    const btn = document.getElementById('btn-update-software');
    const status = document.getElementById('update-status');

    if (!btn || !status) return;

    btn.disabled = true;
    btn.textContent = 'Actualizando...';
    status.classList.remove('hidden', 'status-error');
    status.textContent = 'Dispositivo actualizándose. El servicio se reiniciará y la página se recargará en unos segundos.';

    try {
        const response = await fetch('/api/admin/update', { method: 'POST' });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || 'No se pudo iniciar la actualización.');
        }

        status.textContent = result.message + ' Reiniciando servicio...';
        setTimeout(() => {
            location.reload();
        }, 12000);
    } catch (err) {
        console.error('Error al actualizar software:', err);
        btn.disabled = false;
        btn.textContent = 'Actualizar Software';
        status.classList.add('status-error');
        status.textContent = err.message || 'No se pudo iniciar la actualización.';
    }
}

async function triggerSystemReboot() {
    const btn = document.getElementById('btn-reboot-system');
    const status = document.getElementById('reboot-status');

    if (!btn || !status) return;

    const confirmed = window.confirm('La Raspberry Pi se reiniciará y el streaming se interrumpirá. ¿Continuar?');
    if (!confirmed) return;

    btn.disabled = true;
    btn.textContent = 'Reiniciando...';
    status.classList.remove('hidden', 'status-error');
    status.textContent = 'Reinicio solicitado. La página dejará de responder durante el arranque.';

    try {
        const response = await fetch('/api/admin/reboot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirm: true })
        });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || 'No se pudo iniciar el reinicio.');
        }

        status.textContent = result.message;
    } catch (err) {
        console.error('Error al reiniciar Raspberry Pi:', err);
        btn.disabled = false;
        btn.textContent = 'Reiniciar Raspberry Pi';
        status.classList.add('status-error');
        status.textContent = err.message || 'No se pudo iniciar el reinicio.';
    }
}

async function updateCameraSettings(data) {
    try {
        const response = await fetch(cameraApiUrl('/update_settings'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        console.log("Configuración actualizada:", result);
        return result;
    } catch (err) {
        console.error("Error actualizando cámara:", err);
        return null;
    }
}

function parseValue(value, type) {
    if (type === 'boolean') return value === 'true';
    if (type === 'integer') return parseInt(value, 10);
    if (type === 'float') return parseFloat(value);
    return value;
}

function applyVideoRotation(angle) {
    const videoFeed = document.getElementById('video-feed');
    if (!videoFeed) return;

    videoFeed.classList.remove('rotate-90', 'rotate-180', 'rotate-270');

    if (angle === 90) {
        videoFeed.classList.add('rotate-90');
    } else if (angle === 180) {
        videoFeed.classList.add('rotate-180');
    } else if (angle === 270) {
        videoFeed.classList.add('rotate-270');
    }
}

async function setRotation(angle) {
    const parsedAngle = parseInt(angle, 10);
    const result = await updateCameraSettings({ rotation: parsedAngle });
    if (result) {
        applyVideoRotation(parseInt(result.display_rotation || 0, 10));
    }
}

let timelapseRunning = false;

async function toggleTimelapse() {
    const btn = document.getElementById('btn-timelapse');
    const interval = document.getElementById('tl-interval').value;
    const tw = document.getElementById('tl-w').value;
    const th = document.getElementById('tl-h').value;
    const statusDiv = document.getElementById('timelapse-status');

    timelapseRunning = !timelapseRunning;

    if (timelapseRunning) {
        btn.textContent = "Detener Timelapse";
        btn.style.background = "#ff4444";
        statusDiv.classList.remove('hidden');
        
        await updateCameraSettings({ 
            'timelapse': 'start', 
            'interval': parseInt(interval),
            't_width': parseInt(tw),
            't_height': parseInt(th)
        });
    } else {
        btn.textContent = "Iniciar Timelapse";
        btn.style.background = "#00ff88";
        statusDiv.classList.add('hidden');
        await updateCameraSettings({ 'timelapse': 'stop' });
    }
}


/**
 * Centralized event handling and initialization.
 */
function setupEventListeners() {
    document.body.addEventListener('click', (e) => {
        const actionTarget = e.target.closest('[data-action]');
        const action = actionTarget ? actionTarget.dataset.action : null;
        if (!action) {
            // Check for group actions (like rotation buttons)
            const group = e.target.closest('[data-action-group]');
            if (group) {
                const groupAction = group.dataset.actionGroup;
                const valueTarget = e.target.closest('[data-value]');
                const value = valueTarget ? valueTarget.dataset.value : null;
                if (!value) return;
                if (groupAction === 'set-rotation') setRotation(value);
                if (groupAction === 'esp32-move') sendEsp32Move(value);
            }
            return;
        }

        switch (action) {
            case 'toggle-controls': toggleControlPanel(); break;
            case 'apply-custom-resolution': applyCustomResolution(); break;
            case 'capture-custom-photo': captureCustomPhoto(); break;
            case 'reset-camera': resetCamera(); break;
            case 'update-software': triggerSoftwareUpdate(); break;
            case 'reboot-system': triggerSystemReboot(); break;
            case 'toggle-timelapse': toggleTimelapse(); break;
            case 'esp32-connect': connectEsp32(); break;
            case 'esp32-disconnect': disconnectEsp32(); break;
            case 'esp32-center': sendEsp32Center(); break;
            case 'esp32-save-current-position': saveEsp32CurrentPosition(); break;
            case 'esp32-return-position': returnEsp32ToSavedPosition(); break;
            case 'add-tuya-device': addTuyaDevice(); break;
            case 'save-tuya-device-name': saveTuyaDeviceName(actionTarget.dataset.deviceId); break;
            case 'refresh-tuya-device-details': refreshTuyaDeviceDetails(actionTarget.dataset.deviceId); break;
            case 'esp32-send-custom-command': sendEsp32CustomCommand(); break;
        }
    });

    document.body.addEventListener('change', (e) => {
        const action = e.target.dataset.action;
        const control = e.target.dataset.control;

        if (action === 'set-resolution-preset') {
            handleResolutionChange(e.target.value);
        } else if (action === 'apply-preset') {
            applyPreset(e.target.value);
        } else if (action === 'esp32-set-speed') {
            setEsp32Speed(e.target.value);
        } else if (action === 'toggle-tuya-device') {
            toggleTuyaPlug(e);
        } else if (control) {
            const valueType = e.target.dataset.type || (e.target.step ? 'float' : 'string');
            const value = parseValue(e.target.value, valueType);
            updateCameraSettings({ [control]: value });
        }
    });

    // Debounced slider updates
    let sliderTimeout;
    document.querySelectorAll('.camera-slider').forEach(slider => {
        slider.addEventListener('input', (e) => {
            const display = document.getElementById(`val-${e.target.id}`);
            if (display) display.innerText = e.target.value;

            clearTimeout(sliderTimeout);
            sliderTimeout = setTimeout(() => {
                const control = e.target.dataset.control || e.target.id;
                const valueType = e.target.dataset.type || 'float';
                const value = parseValue(e.target.value, valueType);
                updateCameraSettings({ [control]: value });
            }, 50);
        });
    });

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
    });
}


async function initializeDashboard() {
    setupEventListeners();
    restoreControlPanelState();
    await initCameraSpecs();
    await checkCameraCapabilities();
    await refreshEsp32Status();
    await refreshTuyaStatus();

    setInterval(refreshEsp32Status, 3000);
    setInterval(() => {
        if (!document.hidden) {
            refreshTuyaStatus();
        }
    }, 15000);

    // Initial check for AF support to hide elements if needed
    const res = await fetch(cameraApiUrl('/camera_status'));
    const status = await res.json();
    hydrateCameraControls(status);
    if (!status.af_supported) {
        const afControl = document.getElementById('AfModeDiv');
        if (afControl) afControl.style.display = 'none';
    }
}

window.addEventListener('load', initializeDashboard);
