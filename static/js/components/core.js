const CAMERA_API_BASE = '/api/camera';
let esp32LightOn = false;
let esp32LightIntensity = 0;
let lastNonZeroLightIntensity = 100;
let esp32Connected = false;

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
