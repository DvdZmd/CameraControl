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
        alert(`Cambiando a resolución personalizada: ${w}x${h}`);
    }
}

window.addEventListener('load', async () => {
    // 1. Obtener capacidades y límites
    await initCameraSpecs(); 
    // 2. Verificar AF para mostrar/ocultar sliders
    await checkCameraCapabilities(); 
});

async function capturePhoto() {
    try {
        const response = await fetch('/take_photo');
        if (!response.ok) throw new Error('Error en la captura');
        
        // Convertimos la respuesta en un Blob (datos binarios)
        const blob = await response.blob();
        
        // Creamos un enlace temporal en memoria
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        // Extraemos el nombre del archivo del header o ponemos uno por defecto
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        a.download = `snapshot_${timestamp}.jpg`;
        
        document.body.appendChild(a);
        a.click(); // Simulamos el click para descargar
        
        // Limpiamos
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        console.log("Foto capturada con éxito sin interrumpir el stream.");
    } catch (err) {
        console.error("Error al capturar foto:", err);
        alert("Error al capturar la foto.");
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

async function updateCameraSettings(data) {
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
    const interval = document.getElementById('interval').value;
    const statusDiv = document.getElementById('timelapse-status');

    timelapseRunning = !timelapseRunning;

    if (timelapseRunning) {
        btn.textContent = "Detener Timelapse";
        btn.style.background = "#ff4444";
        statusDiv.classList.remove('hidden');
        await updateCameraSettings({ 'timelapse': 'start', 'interval': interval });
    } else {
        btn.textContent = "Iniciar Timelapse";
        btn.style.background = "#00ff88";
        statusDiv.classList.add('hidden');
        await updateCameraSettings({ 'timelapse': 'stop' });
    }
}