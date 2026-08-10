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
