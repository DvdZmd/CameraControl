# camera/timelapse.py
import os
import cv2
import time
from datetime import datetime
from threading import Event, Thread
from config import AVAILABLE_RESOLUTIONS, TIMELAPSE_DIR
from camera.picam import camera_controller
from database.models import TimelapseConfig, db
from logs.logging_config import logger


timelapse_thread = None
timelapse_stop_event = Event()

current_timelapse_config = {
    "interval_minutes": None,
    "width": None,
    "height": None
}

def is_timelapse_running():
    global timelapse_thread
    return timelapse_thread is not None and timelapse_thread.is_alive()

def save_timelapse_config(interval_minutes, width, height, running):
    config = TimelapseConfig.query.first()
    if not config:
        config = TimelapseConfig(
            interval_minutes=interval_minutes,
            width=width,
            height=height,
            is_running=running,
            updated_at=datetime.utcnow()
        )
        db.session.add(config)
    else:
        config.interval_minutes = interval_minutes
        config.width = width
        config.height = height
        config.is_running = running
        config.updated_at = datetime.utcnow()

    db.session.commit()


def start_timelapse(interval_minutes, width, height):
    global timelapse_thread, timelapse_stop_event, current_timelapse_config

    if not camera_controller.picam2:
        logger.warning("[Timelapse] Cannot start timelapse - camera not available")
        return False
        
    if timelapse_thread and timelapse_thread.is_alive():
        return False  # Already running

    current_timelapse_config.update({
        "interval_minutes": interval_minutes,
        "width": width,
        "height": height
    })

    timelapse_stop_event.clear()
    timelapse_thread = Thread(
        target=_timelapse_worker,
        args=(interval_minutes, width, height),
        daemon=True
    )
    timelapse_thread.start()
    save_timelapse_config(interval_minutes, width, height, True)

    return True

def load_saved_config():
    global current_timelapse_config
    config = TimelapseConfig.query.first()
    if config and config.is_running:
        current_timelapse_config.update({
            "interval_minutes": config.interval_minutes,
            "width": config.width,
            "height": config.height
        })
        logger.info(f"[Timelapse] Loaded config: every {config.interval_minutes}m at {config.width}x{config.height}")
        start_timelapse(
            config.interval_minutes,
            config.width,
            config.height
        )

def get_timelapse_config():
    config = TimelapseConfig.query.first()
    if config:
        return {
            "running": config.is_running,
            "interval_minutes": config.interval_minutes,
            "width": config.width,
            "height": config.height,
            "last_updated": config.updated_at.isoformat()
        }
    return {
        "running": False,
        "interval_minutes": None,
        "width": None,
        "height": None
    }


def stop_timelapse():
    global timelapse_thread, timelapse_stop_event

    if timelapse_thread and timelapse_thread.is_alive():
        timelapse_stop_event.set()
        timelapse_thread.join()
        current_timelapse_config.update({
            "interval_minutes": None,
            "width": None,
            "height": None
        })
        save_timelapse_config(0, 0, 0, False)
        return True
    return False

def _timelapse_worker(interval_minutes, width, height):
    """Timelapse worker thread using CameraController"""
    original_resolution = camera_controller.get_current_resolution()
    original_mode = camera_controller.is_still_mode
    
    logger.info(f"[Timelapse] Starting timelapse: {interval_minutes}min intervals at {width}x{height}")
    
    while not timelapse_stop_event.is_set():
        try:
            resolution = (width, height)

            if resolution not in AVAILABLE_RESOLUTIONS:
                logger.error(f"[Timelapse] Unsupported resolution: {resolution}")
                break

            # Set resolution and switch to still mode for better quality
            if resolution != camera_controller.get_current_resolution():
                camera_controller.set_resolution(width, height, update_stream=True)
            
            if not camera_controller.is_still_mode:
                camera_controller.switch_to_still_mode()
            
            # Brief pause for camera stabilization
            time.sleep(0.5)

            # Create save directory
            date_folder = datetime.now().strftime("%Y-%m-%d")
            save_folder = os.path.join(TIMELAPSE_DIR, date_folder)
            os.makedirs(save_folder, exist_ok=True)

            # Generate filename
            timestamp = datetime.now().strftime("%H-%M-%S")
            filename = f"timelapse_{timestamp}.jpg"
            filepath = os.path.join(save_folder, filename)

            # Capture image using CameraController
            result = camera_controller.capture_image(filepath)

            if result:
                logger.info(f"[Timelapse] Captured: {filepath}")
            else:
                logger.error(f"[Timelapse] Failed to capture image")

        except Exception as e:
            logger.exception("[Timelapse] Error during image capture")

        # Wait for next interval (or until stop signal)
        if timelapse_stop_event.wait(interval_minutes * 60):
            break

    # Restore original camera settings
    try:
        if original_resolution != camera_controller.get_current_resolution():
            camera_controller.set_resolution(
                original_resolution[0], 
                original_resolution[1], 
                update_stream=True
            )
        
        if original_mode != camera_controller.is_still_mode:
            if original_mode:
                camera_controller.switch_to_still_mode()
            else:
                camera_controller.switch_to_video_mode()
                
        logger.info("[Timelapse] Camera settings restored")
        
    except Exception as e:
        logger.exception("[Timelapse] Error restoring camera settings")

    logger.info("[Timelapse] Stopped")
