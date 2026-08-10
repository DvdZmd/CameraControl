
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

