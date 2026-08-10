
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
            // Range controls are sent by the debounced input handler below.
            // Avoid sending the same value again when the pointer is released.
            if (e.target.matches('input[type="range"]')) return;
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
                const payload = control === 'LensPosition'
                    ? { AfMode: 0, LensPosition: value }
                    : { [control]: value };
                updateCameraSettings(payload);
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
