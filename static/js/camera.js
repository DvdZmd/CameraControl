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

async function refreshEsp32Status() {
    try {
        const response = await fetch('/api/esp32/status');
        const data = await response.json();

        const badge = document.getElementById('esp32-status-badge');
        const deviceName = document.getElementById('esp32-device-name');
        const address = document.getElementById('esp32-address');
        const lastStateEl = document.getElementById('esp32-last-state');

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
            lastStateEl.textContent = lastState.S ? `Perfil Vel. ${lastState.S}` : 'N/A';
        }

        // Sensores Ambientales y de Suelo
        document.getElementById('sensor-dht-temp').textContent = lastState.DT ? `${parseFloat(lastState.DT).toFixed(1)} °C` : '--';
        document.getElementById('sensor-dht-humidity').textContent = lastState.DH ? `${parseFloat(lastState.DH).toFixed(1)} %` : '--';
        document.getElementById('sensor-ds-temp').textContent = lastState.DS ? `${parseFloat(lastState.DS).toFixed(1)} °C` : '--';
        document.getElementById('sensor-soil-percent').textContent = lastState.SP ? `${lastState.SP} %` : '--';
        document.getElementById('sensor-soil-raw').textContent = lastState.SR || '--';

        // Estado de Movimiento (Servos)
        document.getElementById('servo-pan-pulse').textContent = lastState.P || '--';
        document.getElementById('servo-tilt-pulse').textContent = lastState.T || '--';

    } catch (error) {
        console.error('Error obteniendo estado ESP32:', error);
    }
}

async function connectEsp32() {
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

async function sendEsp32Stop() {
    try {
        const response = await fetch('/api/esp32/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: 'STOP' })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'No se pudo enviar STOP');
        }
        showEsp32Feedback('Comando STOP enviado');
        await refreshEsp32Status();
    } catch (error) {
        showEsp32Feedback(error.message || 'No se pudo enviar STOP', true);
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
        const response = await fetch('/api/tuya/status');
        const data = await response.json();

        const badge = document.getElementById('tuya-status-badge');
        const toggle = document.getElementById('tuya-toggle');

        if (!badge || !toggle) return;

        if (data.ok && data.status) {
            const isOn = data.status.switch_1 === true;
            badge.textContent = isOn ? 'Encendido' : 'Apagado';
            badge.className = `device-badge ${isOn ? 'on' : 'off'}`;
            toggle.checked = isOn;
        } else {
            badge.textContent = 'Error';
            badge.className = 'device-badge unknown';
            console.error('Error obteniendo estado de Tuya:', data.error);
        }
    } catch (error) {
        console.error('Error de red obteniendo estado de Tuya:', error);
        const badge = document.getElementById('tuya-status-badge');
        if(badge) {
            badge.textContent = 'Offline';
            badge.className = 'device-badge unknown';
        }
    }
}

async function toggleTuyaPlug(event) {
    const toggle = event.target;
    const newState = toggle.checked;
    const endpoint = newState ? '/api/tuya/on' : '/api/tuya/off';

    try {
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'La operación falló');
        }
        showTuyaFeedback(`Enchufe ${newState ? 'encendido' : 'apagado'}.`);
        await refreshTuyaStatus(); // Refrescar estado para confirmar
    } catch (error) {
        showTuyaFeedback(error.message, true);
        toggle.checked = !newState; // Revertir el cambio visual si hay error
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
        const action = e.target.dataset.action;
        if (!action) {
            // Check for group actions (like rotation buttons)
            const group = e.target.closest('[data-action-group]');
            if (group) {
                const groupAction = group.dataset.actionGroup;
                const value = e.target.dataset.value;
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
            case 'toggle-timelapse': toggleTimelapse(); break;
            case 'esp32-connect': connectEsp32(); break;
            case 'esp32-disconnect': disconnectEsp32(); break;
            case 'esp32-center': sendEsp32Center(); break;
            case 'esp32-stop': sendEsp32Stop(); break;
            case 'toggle-tuya-plug': toggleTuyaPlug(e); break;
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
    setInterval(refreshTuyaStatus, 5000); // Actualizamos el estado del enchufe cada 5 seg

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
