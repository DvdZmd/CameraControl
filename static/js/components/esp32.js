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

