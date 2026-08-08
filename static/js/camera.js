const CAMERA_API_BASE = '/api/camera';
let esp32LightOn = false;
let esp32LightIntensity = 0;
let lastNonZeroLightIntensity = 100;

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

function renderRaspberryStatus(data) {
    const temperature = document.getElementById('pi-temperature');
    const cpuUsage = document.getElementById('pi-cpu-usage');
    const powerStatus = document.getElementById('pi-power-status');
    const powerValue = document.getElementById('pi-power-value');
    if (temperature) {
        temperature.textContent = Number.isFinite(data.cpu_temperature_c)
            ? `${data.cpu_temperature_c.toFixed(1)} °C`
            : 'N/D';
    }
    if (cpuUsage) {
        cpuUsage.textContent = Number.isFinite(data.cpu_usage_percent)
            ? `${data.cpu_usage_percent.toFixed(1)}%`
            : '--';
    }
    if (!powerStatus || !powerValue) return;
    powerStatus.classList.remove('status-ok', 'status-warning', 'status-danger', 'status-unknown');
    if (!data.power) {
        powerStatus.classList.add('status-unknown');
        powerValue.textContent = 'N/D';
    } else if (data.power.undervoltage_now) {
        powerStatus.classList.add('status-danger');
        powerValue.textContent = 'Bajo voltaje';
    } else if (data.power.undervoltage_occurred) {
        powerStatus.classList.add('status-warning');
        powerValue.textContent = 'Falla previa';
    } else {
        powerStatus.classList.add('status-ok');
        powerValue.textContent = 'OK';
    }
}

async function refreshRaspberryStatus() {
    try {
        const response = await fetch('/api/admin/system-status');
        const data = await response.json();
        if (!response.ok) throw new Error('No se pudo consultar la Raspberry Pi');
        renderRaspberryStatus(data);
    } catch (error) {
        renderRaspberryStatus({
            cpu_temperature_c: null,
            cpu_usage_percent: null,
            power: null
        });
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

function formatAxisPosition(position) {
    if (!position) {
        return '--';
    }

    const pulse = position.pulse_us ?? position.pulse;
    const angle = position.angle_deg ?? position.angle;
    if (pulse === null || pulse === undefined) {
        return '--';
    }
    if (angle === null || angle === undefined) {
        return `${pulse} us`;
    }

    return `${pulse} us / ${Number(angle).toFixed(1)}°`;
}

function formatPositionDetails(positionDetails, fallbackPosition = null) {
    if (positionDetails && positionDetails.pan && positionDetails.tilt) {
        return `P ${formatAxisPosition(positionDetails.pan)} / T ${formatAxisPosition(positionDetails.tilt)}`;
    }

    return formatSavedPosition(fallbackPosition);
}

function normalizeSpeedMode(value) {
    if (value === null || value === undefined || value === '') {
        return null;
    }
    const mode = Number(value);
    return Number.isInteger(mode) && mode >= 0 && mode <= 4 ? String(mode) : null;
}

function renderEsp32Light(intensity, savedIntensity = null) {
    const normalizedIntensity = Math.max(0, Math.min(100, Number(intensity) || 0));
    const normalizedSavedIntensity = Number(savedIntensity);
    if (
        Number.isInteger(normalizedSavedIntensity)
        && normalizedSavedIntensity >= 1
        && normalizedSavedIntensity <= 100
    ) {
        lastNonZeroLightIntensity = normalizedSavedIntensity;
    }
    esp32LightIntensity = normalizedIntensity;
    esp32LightOn = normalizedIntensity > 0;
    if (esp32LightOn) lastNonZeroLightIntensity = normalizedIntensity;
    const button = document.getElementById('light-toggle-btn');
    const label = document.getElementById('light-toggle-label');
    const slider = document.getElementById('light-intensity-slider');
    const valueLabel = document.getElementById('light-intensity-value');
    if (!button || !label) return;
    button.classList.toggle('active', esp32LightOn);
    button.setAttribute('aria-pressed', String(esp32LightOn));
    label.textContent = esp32LightOn ? 'Apagar luz' : 'Prender luz';
    const displayedIntensity = esp32LightOn
        ? normalizedIntensity
        : lastNonZeroLightIntensity;
    if (slider && document.activeElement !== slider) {
        slider.value = String(displayedIntensity);
    }
    if (valueLabel) valueLabel.textContent = `${displayedIntensity}%`;
}

async function setEsp32LightIntensity(intensity) {
    const normalizedIntensity = Math.max(0, Math.min(100, parseInt(intensity, 10) || 0));
    const slider = document.getElementById('light-intensity-slider');
    if (slider) slider.disabled = true;
    try {
        const response = await fetch('/api/esp32/light', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ intensity: normalizedIntensity })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cambiar la intensidad');
        renderEsp32Light(data.intensity, data.saved_intensity);
        showEsp32Feedback(`Intensidad de luz: ${data.intensity}%`);
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo cambiar la intensidad', true);
        await refreshEsp32Status();
    } finally {
        if (slider) slider.disabled = false;
    }
}

async function toggleEsp32Light() {
    const button = document.getElementById('light-toggle-btn');
    const requestedState = !esp32LightOn;
    if (button) button.disabled = true;
    try {
        const response = await fetch('/api/esp32/light', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ on: requestedState })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cambiar la luz');
        renderEsp32Light(data.intensity, data.saved_intensity);
        showEsp32Feedback(data.light_on ? 'Luz prendida' : 'Luz apagada');
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo cambiar la luz', true);
    } finally {
        if (button) button.disabled = false;
    }
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
        const currentPositionEl = document.getElementById('esp32-current-position');
        const speedSelect = document.getElementById('esp32-speed-select');

        if (badge) {
            badge.textContent = data.connected ? 'Conectado' : 'Desconectado';
            badge.className = `esp32-badge ${data.connected ? 'connected' : 'disconnected'}`;
        }
        
        if (deviceName) deviceName.textContent = data.device_name || '--';
        if (address) address.textContent = data.address || '--';
        
        // Actualizar estado y sensores
        const lastState = data.last_state || {};
        const lightState = stateValue(lastState, 'L');
        const savedLight = data.saved_light || {};
        const savedIntensity = Number(savedLight.intensity);
        if (Number.isInteger(savedIntensity) && savedIntensity >= 1 && savedIntensity <= 100) {
            lastNonZeroLightIntensity = savedIntensity;
        }
        const displayedLight = lightState !== null
            ? lightState
            : (savedLight.light_on ? savedLight.intensity : 0);
        const lightIntensity = Number(displayedLight);
        if (Number.isInteger(lightIntensity) && lightIntensity >= 0 && lightIntensity <= 100) {
            renderEsp32Light(lightIntensity, savedIntensity);
        }
        if (lastStateEl) {
            // La clave para velocidad es 'S'
            const speedMode = stateValue(lastState, 'S') ?? data.current_speed_mode ?? data.saved_speed_mode;
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
        const currentPosition = data.current_position || {};
        document.getElementById('servo-pan-pulse').textContent = formatAxisPosition(
            currentPosition.pan || (panPulse !== null ? { pulse_us: panPulse, angle_deg: null } : null)
        );
        document.getElementById('servo-tilt-pulse').textContent = formatAxisPosition(
            currentPosition.tilt || (tiltPulse !== null ? { pulse_us: tiltPulse, angle_deg: null } : null)
        );
        if (currentPositionEl) {
            currentPositionEl.textContent = formatPositionDetails(data.current_position);
        }
        if (savedPositionEl) {
            savedPositionEl.textContent = formatPositionDetails(data.saved_position_details, data.saved_position);
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
            savedPositionEl.textContent = formatPositionDetails(data.saved_position_details, data.saved_position);
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

const expandedTuyaDevices = new Set();
const tuyaStatusByDevice = new Map();

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
        const deviceKey = String(device.id);
        const cachedStatus = tuyaStatusByDevice.get(deviceKey) || {};
        const deviceView = { ...cachedStatus, ...device };
        const isOn = deviceView.is_on === true;
        const hasKnownState = deviceView.status_ok === true;
        const statusText = hasKnownState
            ? (isOn ? 'Encendido' : 'Apagado')
            : 'Estado no consultado';
        const expanded = expandedTuyaDevices.has(deviceKey);
        const tuyaName = deviceView.tuya_name
            ? `<span>Tuya: ${escapeHtml(deviceView.tuya_name)}</span>`
            : '<span>Tuya: sin nombre remoto</span>';
        const editedName = editingState.names.get(String(device.id));
        const displayName = editedName !== undefined ? editedName : deviceView.name;
        const telemetry = renderTuyaTelemetry(deviceView);
        const settings = renderTuyaSettings(deviceView);
        const error = deviceView.status_ok === false ? `<p class="tuya-error">${escapeHtml(deviceView.error || 'No se pudo consultar Tuya')}</p>` : '';
        return `
            <div class="tuya-device-card">
                <div class="tuya-device-summary">
                    <button
                        type="button"
                        class="tuya-expand-button"
                        data-action="toggle-tuya-device-details"
                        data-device-id="${device.id}"
                        aria-expanded="${expanded ? 'true' : 'false'}"
                        aria-controls="tuya-device-details-${device.id}"
                        title="${expanded ? 'Ocultar detalles' : 'Mostrar detalles'}"
                    >
                        <span aria-hidden="true">›</span>
                    </button>
                    <strong>${escapeHtml(deviceView.name)}</strong>
                    <span class="tuya-muted">${escapeHtml(statusText)}</span>
                    <div class="tuya-power-buttons">
                        <button type="button" data-action="set-tuya-device-power" data-device-id="${device.id}" data-state="on">Encender</button>
                        <button type="button" data-action="set-tuya-device-power" data-device-id="${device.id}" data-state="off">Apagar</button>
                    </div>
                </div>
                <div
                    id="tuya-device-details-${device.id}"
                    class="tuya-device-details${expanded ? '' : ' hidden'}"
                >
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
                        <button type="button" data-action="refresh-tuya-device-status" data-device-id="${device.id}">Consultar estado</button>
                        <button type="button" data-action="refresh-tuya-device-details" data-device-id="${device.id}">Refrescar Tuya</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    restoreTuyaNameFocus(editingState);
}

function toggleTuyaDeviceDetails(deviceId) {
    if (!deviceId) return;

    const deviceKey = String(deviceId);
    if (expandedTuyaDevices.has(deviceKey)) {
        expandedTuyaDevices.delete(deviceKey);
    } else {
        expandedTuyaDevices.add(deviceKey);
    }

    const details = document.getElementById(`tuya-device-details-${deviceId}`);
    const button = document.querySelector(`[data-action="toggle-tuya-device-details"][data-device-id="${deviceId}"]`);
    const expanded = expandedTuyaDevices.has(deviceKey);

    if (details) {
        details.classList.toggle('hidden', !expanded);
    }
    if (button) {
        button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        button.title = expanded ? 'Ocultar detalles' : 'Mostrar detalles';
    }
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

    if (device.command_only) {
        return '<p class="tuya-muted">Estado local basado en el ultimo comando enviado. Consultar estado pide el dato real a Tuya Cloud.</p>';
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

async function setTuyaPlugPower(deviceId, newState) {
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
        const deviceKey = String(deviceId);
        const previous = tuyaStatusByDevice.get(deviceKey) || {};
        tuyaStatusByDevice.set(deviceKey, {
            ...previous,
            id: Number(deviceId),
            status_ok: true,
            is_on: newState,
            switch: {
                ...(previous.switch || {}),
                is_on: newState,
            },
            command_only: true,
        });
        showTuyaFeedback(`Dispositivo ${newState ? 'encendido' : 'apagado'}.`);
        await refreshTuyaStatus();
    } catch (error) {
        showTuyaFeedback(error.message, true);
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

async function refreshTuyaDeviceStatus(deviceId) {
    try {
        const response = await fetch(`/api/tuya/devices/${deviceId}/status`);
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'No se pudo consultar el estado de Tuya.');
        }

        tuyaStatusByDevice.set(String(deviceId), data.device);
        showTuyaFeedback('Estado de Tuya actualizado.');
        await refreshTuyaStatus();
    } catch (error) {
        showTuyaFeedback(error.message || 'No se pudo consultar el estado de Tuya.', true);
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
let cameraAvailable = false;
let cameraStreamEnabled = false;

function setCameraStreamUi(enabled, detail) {
    cameraStreamEnabled = enabled;

    const video = document.getElementById('video-feed');
    const placeholder = document.getElementById('camera-placeholder');
    const placeholderDetail = document.getElementById('camera-placeholder-detail');
    const status = document.getElementById('connection-status');
    const toggle = document.getElementById('stream-toggle-btn');

    if (video) {
        if (enabled) {
            const streamUrl = video.dataset.streamUrl || cameraApiUrl('/video_feed');
            video.src = `${streamUrl}?t=${Date.now()}`;
        } else {
            video.removeAttribute('src');
        }
    }

    if (placeholder) {
        placeholder.classList.toggle('hidden', enabled);
    }
    if (placeholderDetail && detail) {
        placeholderDetail.textContent = detail;
    }
    if (status) {
        status.textContent = enabled ? '● LIVE' : '● STREAM OFF';
        status.className = enabled ? 'status-online' : 'status-offline';
    }
    if (toggle) {
        toggle.textContent = enabled ? 'Apagar stream' : 'Prender stream';
        toggle.classList.toggle('active', enabled);
        toggle.disabled = false;
    }
}

function setCameraUnavailable(message) {
    cameraAvailable = false;
    setCameraStreamUi(false, message || 'Cámara no disponible. El resto de la app sigue operativo.');
}

async function fetchCameraStatus() {
    const response = await fetch(cameraApiUrl('/camera_status'));
    const data = await response.json();
    if (!response.ok || data.available === false) {
        throw new Error(data.message || data.error || 'Cámara no disponible');
    }
    cameraAvailable = true;
    setCameraStreamUi(Boolean(data.stream_enabled), data.stream_enabled ? '' : 'Streaming apagado.');
    return data;
}

async function toggleCameraStream() {
    const toggle = document.getElementById('stream-toggle-btn');
    if (toggle) toggle.disabled = true;

    const shouldEnable = !cameraStreamEnabled;
    try {
        const response = await fetch(
            cameraApiUrl(shouldEnable ? '/stream/start' : '/stream/stop'),
            { method: 'POST' }
        );
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || 'No se pudo cambiar el estado del stream');
        }

        setCameraStreamUi(shouldEnable, shouldEnable ? '' : 'Streaming apagado.');
        if (shouldEnable) {
            const status = await fetchCameraStatus();
            hydrateCameraControls(status);
        }
    } catch (error) {
        console.error('Error cambiando streaming:', error);
        setCameraUnavailable(error.message);
    } finally {
        if (toggle) toggle.disabled = false;
    }
}

async function initCameraSpecs() {
    let data;
    try {
        data = await fetchCameraStatus();
    } catch (error) {
        setCameraUnavailable(error.message);
        return null;
    }
    
    cameraMaxW = data.max_width || cameraMaxW;
    cameraMaxH = data.max_height || cameraMaxH;
    
    // Mostramos al usuario el límite real de su cámara
    document.getElementById('max-res-hint').innerText = 
        `Límite del sensor: ${cameraMaxW} x ${cameraMaxH}`;
        
    // Si la cámara es una V3, el límite será aprox 4608x2592
    // Si es una V2, será 3280x2464
    return data;
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
    const wasStreaming = cameraStreamEnabled;
    
    // Indicador visual de que el stream se pausa para capturar
    if (video) video.style.opacity = "0.3";
    
    try {
        // Construimos la URL con los parámetros custom
        const response = await fetch(cameraApiUrl(`/take_photo_custom?w=${w}&h=${h}`));
        if (!response.ok) throw new Error("Error en la captura");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const capturedAt = new Date();
        const pad = value => String(value).padStart(2, '0');
        a.download = [
            capturedAt.getFullYear(),
            pad(capturedAt.getMonth() + 1),
            pad(capturedAt.getDate())
        ].join('_') + '_' + [
            pad(capturedAt.getHours()),
            pad(capturedAt.getMinutes()),
            pad(capturedAt.getSeconds())
        ].join('-') + '.jpg';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error(err);
    } finally {
        // Restauramos la opacidad y forzamos al navegador a reconectar el stream MJPEG
        if (video) video.style.opacity = "1";
        if (wasStreaming && video) {
            setTimeout(() => {
                const streamUrl = video.dataset.streamUrl || cameraApiUrl('/video_feed');
                video.src = streamUrl + '?t=' + new Date().getTime();
            }, 1000); // Damos un segundo para que la cámara termine de re-inicializarse
        }
    }
}


// Función para manejar la visibilidad de los controles según el hardware
async function checkCameraCapabilities() {
    try {
        const status = await fetchCameraStatus();
        
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
        setCameraUnavailable(e.message);
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
        if (!response.ok) {
            throw new Error(result.message || 'No se pudo actualizar la cámara');
        }
        console.log("Configuración actualizada:", result);
        return result;
    } catch (err) {
        console.error("Error actualizando cámara:", err);
        if (!cameraAvailable) {
            setCameraUnavailable(err.message);
        }
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
        'tl-light-warmup', 'tl-resolution-preset', 'tl-save-sensor-readings'].forEach(id => {
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
    document.getElementById('tl-save-sensor-readings').checked = Boolean(data.save_sensor_readings);
    document.getElementById('tl-light-enabled').checked = Boolean(data.light_enabled);
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
    if (select.value) await loadTimelapseCaptures();
}

async function loadTimelapseCaptures() {
    const folder = selectedTimelapseFolder();
    const body = document.getElementById('tl-captures-body');
    const feedback = document.getElementById('tl-captures-feedback');
    body.replaceChildren();
    document.getElementById('tl-select-all-captures').checked = false;
    if (!folder) {
        feedback.classList.remove('hidden', 'status-error');
        feedback.textContent = 'No hay directorios de timelapse';
        return;
    }
    try {
        const params = new URLSearchParams({ folder });
        const response = await fetch(`/api/timelapse/captures?${params}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudieron consultar las capturas');
        data.captures.forEach(capture => {
            const row = document.createElement('tr');
            const selectorCell = document.createElement('td');
            const selector = document.createElement('input');
            selector.type = 'checkbox';
            selector.className = 'tl-capture-selector';
            selector.value = capture.path;
            selectorCell.appendChild(selector);
            const values = [
                capture.name,
                capture.path,
                formatFileSize(capture.size_bytes),
                new Date(capture.modified_at).toLocaleString()
            ];
            row.appendChild(selectorCell);
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
    await loadTimelapseCaptures();
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
            case 'toggle-camera-stream': toggleCameraStream(); break;
            case 'toggle-esp32-light': toggleEsp32Light(); break;
            case 'apply-custom-resolution': applyCustomResolution(); break;
            case 'capture-custom-photo': captureCustomPhoto(); break;
            case 'reset-camera': resetCamera(); break;
            case 'update-software': triggerSoftwareUpdate(); break;
            case 'reboot-system': triggerSystemReboot(); break;
            case 'toggle-timelapse': toggleTimelapse(); break;
            case 'save-timelapse-config':
                saveTimelapseConfig().catch(error => {
                    const feedback = document.getElementById('timelapse-status');
                    feedback.classList.remove('hidden');
                    feedback.classList.add('status-error');
                    feedback.textContent = error.message;
                });
                break;
            case 'load-sensor-history': loadSensorHistory(1); break;
            case 'save-sensor-logging-config': saveSensorLoggingConfig(); break;
            case 'refresh-timelapse-captures': loadTimelapseFolders(); break;
            case 'download-timelapse-folder': downloadTimelapseFolder(); break;
            case 'download-timelapse-capture':
                downloadTimelapseCapture(actionTarget.dataset.capturePath);
                break;
            case 'download-selected-captures':
                downloadSelectedCaptures().catch(error => {
                    const feedback = document.getElementById('tl-captures-feedback');
                    feedback.classList.remove('hidden');
                    feedback.classList.add('status-error');
                    feedback.textContent = error.message;
                });
                break;
            case 'delete-selected-captures':
            case 'delete-timelapse-folder': {
                const operation = action === 'delete-selected-captures'
                    ? deleteSelectedCaptures()
                    : deleteTimelapseFolder();
                operation.catch(error => {
                    const feedback = document.getElementById('tl-captures-feedback');
                    feedback.classList.remove('hidden');
                    feedback.classList.add('status-error');
                    feedback.textContent = error.message;
                });
                break;
            }
            case 'delete-selected-readings':
            case 'delete-all-readings': {
                const operation = action === 'delete-selected-readings'
                    ? deleteSelectedSensorReadings()
                    : deleteAllSensorReadings();
                operation.catch(error => {
                    const feedback = document.getElementById('sensor-history-feedback');
                    feedback.classList.remove('hidden');
                    feedback.classList.add('status-error');
                    feedback.textContent = error.message;
                });
                break;
            }
            case 'esp32-connect': connectEsp32(); break;
            case 'esp32-disconnect': disconnectEsp32(); break;
            case 'esp32-center': sendEsp32Center(); break;
            case 'esp32-save-current-position': saveEsp32CurrentPosition(); break;
            case 'esp32-return-position': returnEsp32ToSavedPosition(); break;
            case 'add-tuya-device': addTuyaDevice(); break;
            case 'save-tuya-device-name': saveTuyaDeviceName(actionTarget.dataset.deviceId); break;
            case 'set-tuya-device-power': setTuyaPlugPower(actionTarget.dataset.deviceId, actionTarget.dataset.state === 'on'); break;
            case 'refresh-tuya-device-status': refreshTuyaDeviceStatus(actionTarget.dataset.deviceId); break;
            case 'refresh-tuya-device-details': refreshTuyaDeviceDetails(actionTarget.dataset.deviceId); break;
            case 'toggle-tuya-device-details': toggleTuyaDeviceDetails(actionTarget.dataset.deviceId); break;
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
        } else if (action === 'set-light-intensity') {
            setEsp32LightIntensity(e.target.value);
        } else if (e.target.id === 'tl-resolution-preset') {
            const custom = e.target.value === 'custom';
            document.getElementById('tl-custom-resolution').style.display = custom ? 'flex' : 'none';
            if (!custom) {
                const [width, height] = e.target.value.split('x').map(Number);
                document.getElementById('tl-w').value = width;
                document.getElementById('tl-h').value = height;
            }
        } else if (
            e.target.id === 'tl-light-enabled'
            || e.target.id === 'tl-light-warmup'
            || e.target.id === 'tl-interval-unit'
        ) {
            syncTimelapseIntervalMinimum();
        } else if (e.target.id === 'tl-folder-select') {
            document.getElementById('tl-folder-name').value = e.target.value;
            loadTimelapseCaptures();
        } else if (e.target.id === 'tl-select-all-captures') {
            document.querySelectorAll('.tl-capture-selector').forEach(input => {
                input.checked = e.target.checked;
            });
        } else if (e.target.id === 'sensor-select-all-readings') {
            document.querySelectorAll('.sensor-reading-selector').forEach(input => {
                input.checked = e.target.checked;
            });
        } else if (control) {
            const valueType = e.target.dataset.type || (e.target.step ? 'float' : 'string');
            const value = parseValue(e.target.value, valueType);
            updateCameraSettings({ [control]: value });
        }
    });

    document.body.addEventListener('input', (e) => {
        if (e.target.dataset.action === 'set-light-intensity') {
            const valueLabel = document.getElementById('light-intensity-value');
            if (valueLabel) valueLabel.textContent = `${e.target.value}%`;
        }
        if (e.target.id === 'tl-light-intensity') {
            document.getElementById('tl-light-intensity-value').textContent = `${e.target.value}%`;
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
    const cameraStatus = await initCameraSpecs();
    if (cameraStatus) {
        hydrateCameraControls(cameraStatus);
        await checkCameraCapabilities();
        if (!cameraStatus.af_supported) {
            const afControl = document.getElementById('AfModeDiv');
            if (afControl) afControl.style.display = 'none';
        }
    }
    await refreshEsp32Status();
    await refreshRaspberryStatus();
    setTimeout(refreshRaspberryStatus, 500);
    await refreshTuyaStatus();
    await refreshTimelapseStatus({ hydrate: true });
    await loadTimelapseFolders(document.getElementById('tl-folder-name').value);
    await loadSensorLoggingConfig();

    setInterval(refreshEsp32Status, 3000);
    setInterval(refreshRaspberryStatus, 5000);
    setInterval(refreshTimelapseStatus, 5000);
}

window.addEventListener('load', initializeDashboard);
