
let cameraMaxW = 1280;
let cameraMaxH = 720;
let cameraAvailable = false;
let cameraStreamEnabled = false;
let cameraStreamRefreshTimeout = null;
const CUSTOM_STREAM_RESOLUTION_KEY = 'cameraCustomStreamResolution';
const CUSTOM_PHOTO_RESOLUTION_KEY = 'cameraCustomPhotoResolution';
const PHOTO_RESOLUTION_PRESET_KEY = 'cameraPhotoResolutionPreset';
const LIVE_REFRESH_CONTROLS = new Set(['Brightness', 'Contrast', 'Saturation', 'Sharpness']);

function readStoredResolution(key) {
    try {
        const resolution = JSON.parse(localStorage.getItem(key));
        const width = Number(resolution?.width);
        const height = Number(resolution?.height);
        if (Number.isInteger(width) && width > 0 && Number.isInteger(height) && height > 0) {
            return { width, height };
        }
    } catch (error) {
        console.warn(`No se pudo restaurar ${key}:`, error);
    }
    return null;
}

function storeResolution(key, width, height) {
    if (!Number.isInteger(width) || width <= 0 || !Number.isInteger(height) || height <= 0) return;
    localStorage.setItem(key, JSON.stringify({ width, height }));
}

function setResolutionInputs(widthId, heightId, resolution) {
    if (!resolution) return;
    const width = document.getElementById(widthId);
    const height = document.getElementById(heightId);
    if (width) width.value = resolution.width;
    if (height) height.value = resolution.height;
}

function configureResolutionPresetOptions() {
    ['res-preset', 'photo-res-preset'].forEach(id => {
        const select = document.getElementById(id);
        if (!select) return;
        select.querySelectorAll('option[data-width]').forEach(option => {
            const supported = Number(option.dataset.width) <= cameraMaxW
                && Number(option.dataset.height) <= cameraMaxH;
            option.hidden = !supported;
            option.disabled = !supported;
        });
    });

    const photoPreset = document.getElementById('photo-res-preset');
    const customOption = photoPreset?.querySelector('option[value="custom"]');
    if (!photoPreset || !customOption) return;
    photoPreset.querySelectorAll('option[data-generated="sensor-max"]').forEach(option => option.remove());
    const maxResolution = `${cameraMaxW}x${cameraMaxH}`;
    if (!Array.from(photoPreset.options).some(option => option.value === maxResolution)) {
        const option = document.createElement('option');
        option.value = maxResolution;
        option.dataset.width = String(cameraMaxW);
        option.dataset.height = String(cameraMaxH);
        option.dataset.generated = 'sensor-max';
        option.textContent = `Máxima del sensor (${cameraMaxW}x${cameraMaxH})`;
        photoPreset.insertBefore(option, customOption);
    }
}

function restoreResolutionPreferences() {
    setResolutionInputs('custom-w', 'custom-h', readStoredResolution(CUSTOM_STREAM_RESOLUTION_KEY));
    setResolutionInputs('photo-w', 'photo-h', readStoredResolution(CUSTOM_PHOTO_RESOLUTION_KEY));

    const photoPreset = document.getElementById('photo-res-preset');
    const savedPreset = localStorage.getItem(PHOTO_RESOLUTION_PRESET_KEY) || '1920x1080';
    const savedOption = photoPreset
        ? Array.from(photoPreset.options).find(option => option.value === savedPreset && !option.disabled)
        : null;
    handlePhotoResolutionChange(savedOption ? savedPreset : 'custom', false);
}

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

function refreshCameraStreamImage() {
    if (!cameraStreamEnabled) return;
    clearTimeout(cameraStreamRefreshTimeout);
    cameraStreamRefreshTimeout = setTimeout(() => {
        if (!cameraStreamEnabled) return;
        const video = document.getElementById('video-feed');
        if (!video) return;
        const streamUrl = video.dataset.streamUrl || cameraApiUrl('/video_feed');
        video.src = `${streamUrl}?t=${Date.now()}`;
    }, 150);
}

function setCameraUnavailable(message) {
    cameraAvailable = false;
    setCameraStreamUi(false, message || 'Cámara no disponible. El resto de la app sigue operativo.');
    if (typeof renderHomeCameraHealth === 'function') {
        renderHomeCameraHealth(null, new Error(message || 'Cámara no disponible'));
    }
}

async function fetchCameraStatus() {
    const response = await fetch(cameraApiUrl('/camera_status'));
    const data = await response.json();
    if (!response.ok || data.available === false) {
        throw new Error(data.message || data.error || 'Cámara no disponible');
    }
    cameraAvailable = true;
    setCameraStreamUi(Boolean(data.stream_enabled), data.stream_enabled ? '' : 'Streaming apagado.');
    if (typeof renderHomeCameraHealth === 'function') renderHomeCameraHealth(data);
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
    restoreResolutionPreferences();
    let data;
    try {
        data = await fetchCameraStatus();
    } catch (error) {
        setCameraUnavailable(error.message);
        return null;
    }
    
    cameraMaxW = data.max_width || cameraMaxW;
    cameraMaxH = data.max_height || cameraMaxH;
    configureResolutionPresetOptions();
    restoreResolutionPreferences();
    
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
        setResolutionInputs('custom-w', 'custom-h', readStoredResolution(CUSTOM_STREAM_RESOLUTION_KEY));
    } else {
        customDiv.style.display = 'none';
        const [w, h] = val.split('x');
        updateCameraSettings({ width: parseInt(w), height: parseInt(h) });
    }
}

function handlePhotoResolutionChange(value, persist = true) {
    const preset = document.getElementById('photo-res-preset');
    const customInputs = document.getElementById('photo-custom-res-inputs');
    if (!preset || !customInputs) return;

    preset.value = value;
    if (persist) localStorage.setItem(PHOTO_RESOLUTION_PRESET_KEY, value);
    if (value === 'custom') {
        customInputs.style.display = 'flex';
        setResolutionInputs('photo-w', 'photo-h', readStoredResolution(CUSTOM_PHOTO_RESOLUTION_KEY));
        return;
    }

    const [width, height] = value.split('x').map(Number);
    document.getElementById('photo-w').value = width;
    document.getElementById('photo-h').value = height;
    customInputs.style.display = 'none';
}

function restoreControlPanelState() {
    const panel = document.querySelector('.controls-panel');
    const toggleBtn = document.getElementById('toggle-panel-btn');
    const resizeHandle = document.getElementById('panel-resize-handle');
    const hidden = localStorage.getItem('controlsPanelHidden') === 'true';

    if (hidden) {
        panel.classList.add('hidden');
        panel.style.flexBasis = '0px';
        if (resizeHandle) resizeHandle.classList.add('hidden');
        if (toggleBtn) toggleBtn.textContent = 'Mostrar panel';
    } else {
        panel.classList.remove('hidden');
        const savedWidth = Number(localStorage.getItem('controlsPanelWidth'));
        panel.style.flexBasis = Number.isFinite(savedWidth) && savedWidth > 0 ? `${savedWidth}px` : '';
        if (resizeHandle) resizeHandle.classList.remove('hidden');
        if (toggleBtn) toggleBtn.textContent = 'Ocultar panel';
    }
}

function toggleControlPanel() {
    const panel = document.querySelector('.controls-panel');
    const toggleBtn = document.getElementById('toggle-panel-btn');
    const resizeHandle = document.getElementById('panel-resize-handle');
    const hidden = panel.classList.toggle('hidden');

    if (hidden) {
        panel.style.flexBasis = '0px';
    } else {
        const savedWidth = Number(localStorage.getItem('controlsPanelWidth'));
        panel.style.flexBasis = Number.isFinite(savedWidth) && savedWidth > 0 ? `${savedWidth}px` : '';
    }
    if (resizeHandle) resizeHandle.classList.toggle('hidden', hidden);
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
        document.getElementById('custom-w').value = w;
        document.getElementById('custom-h').value = h;
        storeResolution(CUSTOM_STREAM_RESOLUTION_KEY, w, h);
        updateCameraSettings({ width: w, height: h });
    }
}

async function captureCustomPhoto() {
    const w = document.getElementById('photo-w').value;
    const h = document.getElementById('photo-h').value;
    if (document.getElementById('photo-res-preset').value === 'custom') {
        storeResolution(CUSTOM_PHOTO_RESOLUTION_KEY, Number(w), Number(h));
    }
    const video = document.getElementById('video-feed');
    const wasStreaming = cameraStreamEnabled;
    
    // Indicador visual de que el stream se pausa para capturar
    if (video) video.style.opacity = "0.3";
    
    try {
        // Construimos la URL con los parámetros custom
        const overlay = document.getElementById('manual-capture-overlay')?.checked === true;
        const response = await fetch(cameraApiUrl(`/take_photo_custom?w=${w}&h=${h}&overlay=${overlay}`));
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

function showHomeCaptureFeedback(message, isError = false) {
    const feedback = document.getElementById('home-capture-feedback');
    if (!feedback) return;

    feedback.classList.remove('hidden', 'status-error');
    feedback.classList.toggle('status-error', isError);
    feedback.textContent = message;
}

function captureVisibleFrame() {
    const video = document.getElementById('video-feed');
    const button = document.getElementById('home-capture-frame-btn');
    if (!cameraStreamEnabled || !video || video.naturalWidth === 0 || video.naturalHeight === 0) {
        showHomeCaptureFeedback('El stream debe estar encendido para capturar el frame visible.', true);
        return;
    }

    let rotation = 0;
    if (video.classList.contains('rotate-90')) rotation = 90;
    if (video.classList.contains('rotate-180')) rotation = 180;
    if (video.classList.contains('rotate-270')) rotation = 270;

    const swapsDimensions = rotation === 90 || rotation === 270;
    const canvas = document.createElement('canvas');
    canvas.width = swapsDimensions ? video.naturalHeight : video.naturalWidth;
    canvas.height = swapsDimensions ? video.naturalWidth : video.naturalHeight;

    const context = canvas.getContext('2d');
    if (!context) {
        showHomeCaptureFeedback('El navegador no pudo preparar la captura.', true);
        return;
    }

    try {
        context.translate(canvas.width / 2, canvas.height / 2);
        context.rotate(rotation * Math.PI / 180);
        context.drawImage(video, -video.naturalWidth / 2, -video.naturalHeight / 2);
        context.setTransform(1, 0, 0, 1, 0, 0);
        if (document.getElementById('manual-capture-overlay')?.checked === true) {
            drawManualCaptureOverlay(context, canvas, new Date());
        }
    } catch (error) {
        console.error('Error capturando el frame visible:', error);
        showHomeCaptureFeedback('No se pudo leer el frame actual del stream.', true);
        return;
    }

    if (button) button.disabled = true;
    canvas.toBlob(blob => {
        if (!blob) {
            showHomeCaptureFeedback('No se pudo generar la foto.', true);
            if (button) button.disabled = false;
            return;
        }

        const capturedAt = new Date();
        const pad = value => String(value).padStart(2, '0');
        const filename = [
            capturedAt.getFullYear(),
            pad(capturedAt.getMonth() + 1),
            pad(capturedAt.getDate())
        ].join('_') + '_' + [
            pad(capturedAt.getHours()),
            pad(capturedAt.getMinutes()),
            pad(capturedAt.getSeconds())
        ].join('-') + '_stream.jpg';
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        showHomeCaptureFeedback('Frame capturado.');
        if (button) button.disabled = false;
    }, 'image/jpeg', 0.95);
}

function drawManualCaptureOverlay(context, canvas, capturedAt) {
    const value = id => document.getElementById(id)?.textContent?.trim() || '--';
    const pad = number => String(number).padStart(2, '0');
    const lines = [
        `${pad(capturedAt.getDate())}/${pad(capturedAt.getMonth() + 1)}/${capturedAt.getFullYear()} ${pad(capturedAt.getHours())}:${pad(capturedAt.getMinutes())}:${pad(capturedAt.getSeconds())}`,
        `Temp Ambiente: ${value('home-sensor-dht-temp')}   Humedad Ambiente: ${value('home-sensor-dht-humidity')}`,
        `Temp Cultivo: ${value('home-sensor-ds-temp')}   Humedad Cultivo: ${value('home-sensor-soil-percent')}`
    ];
    const fontSize = Math.max(8, Math.min(30, Math.round(canvas.width * 0.012)));
    const padding = Math.max(8, Math.round(fontSize / 2));
    const spacing = Math.max(3, Math.round(fontSize / 4));
    const lineHeight = Math.round(fontSize * 1.25);
    context.font = `${fontSize}px sans-serif`;
    const width = Math.max(...lines.map(line => context.measureText(line).width));
    const height = lines.length * lineHeight + (lines.length - 1) * spacing;
    const top = canvas.height - height - padding * 2;
    context.fillStyle = 'rgba(0, 0, 0, 0.5)';
    context.fillRect(padding, top, width + padding * 2, height + padding);
    context.fillStyle = 'rgba(255, 255, 255, 0.9)';
    context.textBaseline = 'top';
    lines.forEach((line, index) => {
        context.fillText(line, padding * 2, top + padding + index * (lineHeight + spacing));
    });
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
        const appliedControls = result.applied_controls || [];
        if (result.stream_restarted || appliedControls.some(control => LIVE_REFRESH_CONTROLS.has(control))) {
            refreshCameraStreamImage();
        }
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
