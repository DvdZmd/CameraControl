window.onload = async () => {
    const res = await fetch('/camera_status');
    const status = await res.json();
    
    if (!status.af_supported) {
        // Ocultamos el div de AF si no se soporta
        const afControl = document.getElementById('AfModeDiv');
        if (afControl) afControl.style.display = 'none';
    }
};

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