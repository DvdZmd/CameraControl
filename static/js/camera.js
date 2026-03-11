window.onload = async () => {
    const res = await fetch('/camera_status');
    const status = await res.json();
    
    if (!status.af_supported) {
        // Ocultamos el div de AF si no se soporta
        const afControl = document.getElementById('AfModeDiv');
        if (afControl) afControl.style.display = 'none';
    }
};

let cameraMaxW = 1280;
let cameraMaxH = 720;

async function initCameraSpecs() {
    const res = await fetch('/camera_status');
    const data = await res.json();
    
    cameraMaxW = data.max_width;
    cameraMaxH = data.max_height;
    
    // Mostramos al usuario el límite real de su cámara
    document.getElementById('max-res-hint').innerText = 
        `Límite del sensor: ${cameraMaxW} x ${cameraMaxH}`;
        
    // Si la cámara es una V3, el límite será aprox 4608x2592
    // Si es una V2, será 3280x2464
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

window.addEventListener('load', async () => {
    // 1. Obtener capacidades y límites
    await initCameraSpecs(); 
    // 2. Verificar AF para mostrar/ocultar sliders
    await checkCameraCapabilities(); 
});

async function captureCustomPhoto() {
    const w = document.getElementById('photo-w').value;
    const h = document.getElementById('photo-h').value;
    const video = document.getElementById('video-feed');
    
    // Indicador visual de que el stream se pausa para capturar
    video.style.opacity = "0.3";
    
    try {
        // Construimos la URL con los parámetros custom
        const response = await fetch(`/take_photo_custom?w=${w}&h=${h}`);
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
        const res = await fetch('/camera_status');
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

// Llamar al cargar la página
window.addEventListener('load', checkCameraCapabilities);

// Listener para los Sliders de Calidad de Imagen
let timeout;
document.querySelectorAll('.camera-slider').forEach(slider => {
    slider.addEventListener('input', (e) => {
        const param = e.target.id;
        const value = e.target.value;

        // Cancelamos el envío anterior si el usuario sigue moviendo el slider
        clearTimeout(timeout);
        
        // Solo enviamos el comando después de 50ms de inactividad
        timeout = setTimeout(() => {
            updateCameraSettings({ [param]: parseFloat(value) });
        }, 50);
    });
});;

// Actualizar visualización de valores al mover sliders
document.querySelectorAll('.camera-slider').forEach(slider => {
    slider.addEventListener('input', (e) => {
        const display = document.getElementById(`val-${e.target.id}`);
        if (display) {
            display.innerText = e.target.value;
        }
    });
});

// Aplicar un preset desde el selector
async function applyPreset(presetName) {
    if (!presetName) return;
    
    try {
        const response = await fetch('/apply_preset', {
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
        const response = await fetch('/reset', { method: 'POST' });
        if (response.ok) {
            location.reload();
        }
    } catch (err) {
        console.error("Error al resetear cámara:", err);
    }
}

async function updateCameraSettings(data) {
    // Aseguramos que los tipos sean correctos antes de enviar
    if (data.ExposureTime) data.ExposureTime = parseInt(data.ExposureTime);
    if (data.AnalogueGain) data.AnalogueGain = parseFloat(data.AnalogueGain);

    if (data.AeEnable !== undefined) {
        data.AeEnable = !!data.AeEnable;
    }

    try {
        const response = await fetch('/update_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        console.log("Configuración actualizada:", result);
    } catch (err) {
        console.error("Error actualizando cámara:", err);
    }
}

async function setRotation(angle) {
    await updateCameraSettings({ 'rotation': angle });
    // Nota: Como la rotación por hardware reinicia el stream, 
    // el video-feed de la imagen se reconectará automáticamente.
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