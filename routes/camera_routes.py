import os
import time
import cv2
from datetime import datetime
from threading import Event, Lock
from flask import Blueprint, Response, request, send_file, jsonify, render_template
from config import AVAILABLE_RESOLUTIONS
from camera.picam import camera_controller
from camera.timelapse import start_timelapse, stop_timelapse, get_timelapse_config
from camera.camera_utils import (
    CameraPresets, CameraControlLimits, validate_control_value,
    apply_preset, create_custom_preset, get_focus_distance_estimate,
    calculate_optimal_exposure, generate_focus_steps, get_control_info
)
from logs.logging_config import logger

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/')
def index():
    """Serve the main camera control interface"""
    return render_template('index.html')

timelapse_thread = None
timelapse_stop_event = Event()
camera_stream_enabled = True  # global control
rotation_angle = 0

@camera_bp.route('/toggle_camera', methods=['POST'])
def toggle_camera():
    global camera_stream_enabled
    camera_stream_enabled = not camera_stream_enabled
    return jsonify({
        "enabled": camera_stream_enabled,
        "message": "Camera turned " + ("on" if camera_stream_enabled else "off")
    })

# ======= CAMERA STREAM FUNCTION ===========
def generate_frames():
    frame_count = 0
    while True:
        if not camera_controller.picam2 or not camera_stream_enabled:
            time.sleep(0.1)
            continue

        try:
            frame = camera_controller.picam2.capture_array()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if rotation_angle == 0:
                frame_rotated = frame_rgb
            elif rotation_angle == 90:
                frame_rotated = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
            elif rotation_angle == 180:
                frame_rotated = cv2.rotate(frame_rgb, cv2.ROTATE_180)
            elif rotation_angle == 270:
                frame_rotated = cv2.rotate(frame_rgb, cv2.ROTATE_90_COUNTERCLOCKWISE)

            _, buffer = cv2.imencode('.jpg', frame_rotated)
            
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except Exception as e:
            logger.exception("[Camera Stream] Error capturing frame")
            break

@camera_bp.route('/set_rotation', methods=['POST'])
def set_rotation():
    global rotation_angle
    try:
        data = request.get_json()
        angle = int(data['rotation'])
        if angle in [0, 90, 180, 270]:
            rotation_angle = angle
            return 'OK', 200
        else:
            return 'Invalid angle', 400
    except Exception as e:
        logger.exception("[Camera Stream] Error setting rotation")
        return f'Error: {e}', 500

@camera_bp.route('/video_feed')
def video_feed():
    # Always return a response, even if camera is not available
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@camera_bp.route('/camera_status', methods=['GET'])
def camera_status():
    """Get camera availability and status"""
    return jsonify({
        "available": camera_controller.picam2 is not None,
        "picam2": camera_controller.picam2 is not None,
        "video_config": camera_controller.video_config is not None,
        "stream_enabled": camera_stream_enabled,
        "rotation_angle": rotation_angle,
        "resolution": camera_controller.get_current_resolution() if camera_controller.picam2 else None,
        "mode": "still" if camera_controller.is_still_mode else "video" if camera_controller.picam2 else None
    })

@camera_bp.route('/timelapse_status', methods=['GET'])
def timelapse_status():
    return jsonify(get_timelapse_config())


@camera_bp.route('/timelapse', methods=['POST'])
def handle_timelapse():
    data = request.get_json()
    action = data.get("action")

    if action == "start":
        interval = int(data.get("interval_minutes", 5))
        width = int(data.get("width", 640))
        height = int(data.get("height", 480))

        if start_timelapse(interval, width, height):
            return jsonify({"message": f"✅ Timelapse started every {interval} min at {width}x{height}"}), 200
        else:
            return jsonify({"message": "Timelapse already running"}), 400

    elif action == "stop":
        if stop_timelapse():
            return jsonify({"message": "🛑 Timelapse stopped"}), 200
        else:
            return jsonify({"message": "Timelapse is not running"}), 400

    return jsonify({"message": "Invalid action"}), 400



@camera_bp.route('/set_stream_resolution', methods=['POST'])
def set_stream_resolution():
    """Set camera resolution using CameraController"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        width, height = map(int, data.get("resolution", "640x480").split("x"))
        resolution = (width, height)
        
        if resolution not in AVAILABLE_RESOLUTIONS:
            return jsonify({
                "error": "Unsupported resolution",
                "available_resolutions": AVAILABLE_RESOLUTIONS
            }), 400

        # Use CameraController to set resolution
        success = camera_controller.set_resolution(width, height, update_stream=True)
        
        if success:
            return jsonify({
                "message": f"Stream resolution set to {width}x{height}",
                "resolution": resolution,
                "current_mode": "still" if camera_controller.is_still_mode else "video"
            }), 200
        else:
            return jsonify({"error": "Failed to set resolution"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting stream resolution")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/capture_image', methods=['GET'])
def capture_image():
    """Capture image using CameraController with automatic mode switching"""
    if not camera_controller.picam2:
        return jsonify({
            "error": "Camera not available", 
            "message": "Camera is not connected or not properly configured"
        }), 503

    try:
        width = int(request.args.get("width", 640))
        height = int(request.args.get("height", 480))
        resolution = (width, height)

        if resolution not in AVAILABLE_RESOLUTIONS:
            return jsonify({
                "error": "Unsupported resolution",
                "available_resolutions": AVAILABLE_RESOLUTIONS
            }), 400

        # Prepare folder structure
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
        pictures_dir = os.path.join(root_dir, "Pictures")
        date_folder = datetime.now().strftime("%Y-%m-%d")
        save_folder = os.path.join(pictures_dir, date_folder)
        os.makedirs(save_folder, exist_ok=True)

        # Create filename with current time
        timestamp = datetime.now().strftime("%H-%M-%S")
        filename = f"{timestamp}.jpg"
        filepath = os.path.join(save_folder, filename)

        # Use CameraController to capture with specified resolution
        result = camera_controller.capture_image(filepath, resolution)

        if result:
            logger.info(f"[Camera] Image captured successfully: {filepath}")
            return send_file(filepath, mimetype='image/jpeg', as_attachment=True)
        else:
            return jsonify({"error": "Failed to capture image"}), 500

    except Exception as e:
        logger.exception("[Camera] Error capturing image")
        return jsonify({"error": f"Failed to capture image: {e}"}), 500


# ======= CAMERA CONFIGURATION ENDPOINTS ===========

@camera_bp.route('/camera_controls', methods=['GET'])
def get_camera_controls():
    """Get available camera controls and their current values"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    return jsonify({
        "available_controls": camera_controller.get_available_controls(),
        "current_controls": camera_controller.get_current_controls(),
        "control_info": get_control_info()
    })


@camera_bp.route('/camera_control/<control_name>', methods=['POST'])
def set_camera_control(control_name):
    """Set a single camera control value"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        value = data.get('value')
        
        if value is None:
            return jsonify({"error": "Value is required"}), 400
        
        # Validate the control value
        is_valid, adjusted_value = validate_control_value(control_name, value)
        if not is_valid:
            return jsonify({"error": f"Invalid value for {control_name}"}), 400
        
        # Apply the control
        success = camera_controller.update_control(control_name, adjusted_value)
        if success:
            return jsonify({
                "message": f"Updated {control_name}",
                "control": control_name,
                "value": adjusted_value,
                "original_value": value
            })
        else:
            return jsonify({"error": f"Failed to update {control_name}"}), 500
            
    except Exception as e:
        logger.exception(f"[Camera] Error setting {control_name}")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_controls', methods=['POST'])
def set_multiple_camera_controls():
    """Set multiple camera controls at once"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        controls = data.get('controls', {})
        
        if not controls:
            return jsonify({"error": "Controls dictionary is required"}), 400
        
        # Validate all controls
        validated_controls = {}
        validation_errors = []
        
        for control_name, value in controls.items():
            is_valid, adjusted_value = validate_control_value(control_name, value)
            if is_valid:
                validated_controls[control_name] = adjusted_value
            else:
                validation_errors.append(f"Invalid value for {control_name}: {value}")
        
        if validation_errors:
            return jsonify({"errors": validation_errors}), 400
        
        # Apply all controls
        success = camera_controller.update_multiple_controls(validated_controls)
        if success:
            return jsonify({
                "message": "Updated multiple controls",
                "applied_controls": validated_controls
            })
        else:
            return jsonify({"error": "Failed to update controls"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting multiple controls")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_preset/<preset_name>', methods=['POST'])
def apply_camera_preset(preset_name):
    """Apply a predefined camera preset"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = apply_preset(camera_controller, preset_name)
    if success:
        return jsonify({
            "message": f"Applied preset: {preset_name}",
            "current_controls": camera_controller.get_current_controls()
        })
    else:
        return jsonify({"error": f"Failed to apply preset: {preset_name}"}), 400


@camera_bp.route('/camera_presets', methods=['GET'])
def get_available_presets():
    """Get list of available camera presets"""
    presets = CameraPresets()
    
    return jsonify({
        "presets": {
            "daylight": {
                "name": "Daylight",
                "description": "Optimized for outdoor daylight conditions",
                "controls": presets.DAYLIGHT
            },
            "indoor": {
                "name": "Indoor",
                "description": "Optimized for indoor lighting",
                "controls": presets.INDOOR
            },
            "low_light": {
                "name": "Low Light",
                "description": "Enhanced sensitivity for low light conditions",
                "controls": presets.LOW_LIGHT
            },
            "high_contrast": {
                "name": "High Contrast",
                "description": "Enhanced contrast and sharpness",
                "controls": presets.HIGH_CONTRAST
            },
            "timelapse": {
                "name": "Timelapse",
                "description": "Stable settings for timelapse photography",
                "controls": presets.TIMELAPSE
            }
        }
    })


@camera_bp.route('/camera_focus/manual', methods=['POST'])
def set_manual_focus():
    """Set manual focus position"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        lens_position = float(data.get('lens_position', 0.0))
        
        # Validate lens position
        is_valid, adjusted_position = validate_control_value('LensPosition', lens_position)
        if not is_valid:
            return jsonify({"error": "Invalid lens position"}), 400
        
        success = camera_controller.set_manual_focus(adjusted_position)
        if success:
            distance_estimate = get_focus_distance_estimate(adjusted_position)
            return jsonify({
                "message": "Manual focus set",
                "lens_position": adjusted_position,
                "distance_estimate": distance_estimate
            })
        else:
            return jsonify({"error": "Failed to set manual focus"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting manual focus")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_focus/auto', methods=['POST'])
def set_auto_focus():
    """Set autofocus mode"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        af_mode = int(data.get('mode', 2))  # Default to continuous
        
        success = camera_controller.set_auto_focus(af_mode)
        if success:
            limits = CameraControlLimits()
            mode_name = limits.AF_MODES.get(af_mode, "Unknown")
            return jsonify({
                "message": f"Autofocus mode set to {mode_name}",
                "af_mode": af_mode,
                "mode_name": mode_name
            })
        else:
            return jsonify({"error": "Failed to set autofocus mode"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting autofocus")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_focus/sweep', methods=['POST'])
def focus_sweep():
    """Perform focus sweep and return focus positions"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        start_pos = float(data.get('start', 0.0))
        end_pos = float(data.get('end', 32.0))
        steps = int(data.get('steps', 10))
        
        focus_positions = generate_focus_steps(start_pos, end_pos, steps)
        
        return jsonify({
            "message": "Focus sweep positions generated",
            "positions": focus_positions,
            "start": start_pos,
            "end": end_pos,
            "steps": steps
        })
        
    except Exception as e:
        logger.exception("[Camera] Error generating focus sweep")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_exposure/auto', methods=['POST'])
def set_auto_exposure():
    """Set automatic exposure"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = camera_controller.update_control("ExposureTime", None)
    if success:
        return jsonify({"message": "Automatic exposure enabled"})
    else:
        return jsonify({"error": "Failed to set automatic exposure"}), 500


@camera_bp.route('/camera_exposure/manual', methods=['POST'])
def set_manual_exposure():
    """Set manual exposure time"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        exposure_time = int(data.get('exposure_time'))
        
        # Validate exposure time
        is_valid, adjusted_time = validate_control_value('ExposureTime', exposure_time)
        if not is_valid:
            return jsonify({"error": "Invalid exposure time"}), 400
        
        success = camera_controller.update_control("ExposureTime", adjusted_time)
        if success:
            return jsonify({
                "message": "Manual exposure set",
                "exposure_time": adjusted_time,
                "exposure_ms": adjusted_time / 1000
            })
        else:
            return jsonify({"error": "Failed to set manual exposure"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting manual exposure")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_exposure/scene', methods=['POST'])
def set_scene_exposure():
    """Set exposure based on scene type"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        scene_type = data.get('scene_type', 'auto')
        
        exposure_time = calculate_optimal_exposure(scene_type)
        
        success = camera_controller.update_control("ExposureTime", exposure_time)
        if success:
            return jsonify({
                "message": f"Exposure set for scene: {scene_type}",
                "scene_type": scene_type,
                "exposure_time": exposure_time,
                "exposure_ms": exposure_time / 1000 if exposure_time else "Auto"
            })
        else:
            return jsonify({"error": "Failed to set scene exposure"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting scene exposure")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_reset', methods=['POST'])
def reset_camera_controls():
    """Reset all camera controls to default values"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = camera_controller.reset_to_defaults()
    if success:
        return jsonify({
            "message": "Camera controls reset to defaults",
            "current_controls": camera_controller.get_current_controls(),
            "resolution": camera_controller.get_current_resolution()
        })
    else:
        return jsonify({"error": "Failed to reset camera controls"}), 500


# ======= RESOLUTION AND MODE CONTROL ENDPOINTS ===========

@camera_bp.route('/camera_resolution', methods=['GET'])
def get_camera_resolution():
    """Get current camera resolution and available resolutions"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    return jsonify({
        "current_resolution": camera_controller.get_current_resolution(),
        "available_resolutions": AVAILABLE_RESOLUTIONS,
        "current_mode": "still" if camera_controller.is_still_mode else "video",
        "resolution_limits": {
            "min_width": 64,
            "max_width": 4608,
            "min_height": 64, 
            "max_height": 2592
        }
    })


@camera_bp.route('/camera_resolution/validate', methods=['POST'])
def validate_custom_resolution():
    """Validate if a custom resolution is supported by the camera"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        width = int(data.get('width'))
        height = int(data.get('height'))
        
        # Basic bounds validation
        if width < 64 or width > 4608 or height < 64 or height > 2592:
            return jsonify({
                "valid": False,
                "error": "Resolution out of bounds",
                "limits": "Width: 64-4608, Height: 64-2592"
            })
        
        # Check if it's a standard resolution
        resolution = (width, height)
        is_standard = resolution in AVAILABLE_RESOLUTIONS
        
        # Try to test the resolution (without actually changing camera config)
        try:
            # Create a test configuration to see if camera supports it
            test_config = camera_controller.picam2.create_video_configuration(
                main={"size": resolution}
            )
            
            return jsonify({
                "valid": True,
                "resolution": resolution,
                "is_standard": is_standard,
                "message": "Resolution appears to be supported" if not is_standard else "Standard resolution",
                "aspect_ratio": round(width / height, 2)
            })
            
        except Exception as test_error:
            return jsonify({
                "valid": False,
                "resolution": resolution,
                "error": "Camera does not support this resolution",
                "details": str(test_error)
            })
            
    except Exception as e:
        logger.exception("[Camera] Error validating resolution")
        return jsonify({
            "valid": False,
            "error": str(e)
        }), 500


@camera_bp.route('/camera_resolution', methods=['POST'])
def set_camera_resolution():
    """Set camera resolution using CameraController (supports custom resolutions)"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        width = int(data.get('width'))
        height = int(data.get('height'))
        update_stream = data.get('update_stream', True)
        force_custom = data.get('force_custom', False)  # Allow custom resolutions
        
        resolution = (width, height)
        
        # Validate resolution bounds (reasonable limits for Pi camera)
        if width < 64 or width > 4608 or height < 64 or height > 2592:
            return jsonify({
                "error": "Resolution out of bounds",
                "limits": "Width: 64-4608, Height: 64-2592",
                "requested": f"{width}x{height}"
            }), 400
        
        # Check if resolution is in predefined list or if custom is forced
        if resolution not in AVAILABLE_RESOLUTIONS and not force_custom:
            return jsonify({
                "error": "Non-standard resolution detected",
                "message": "Use force_custom=true to use custom resolution",
                "available_resolutions": AVAILABLE_RESOLUTIONS,
                "requested": resolution
            }), 400
        
        success = camera_controller.set_resolution(width, height, update_stream)
        
        if success:
            is_custom = resolution not in AVAILABLE_RESOLUTIONS
            return jsonify({
                "message": f"Resolution set to {width}x{height}" + (" (custom)" if is_custom else ""),
                "resolution": resolution,
                "is_custom": is_custom,
                "update_stream": update_stream,
                "current_mode": "still" if camera_controller.is_still_mode else "video"
            })
        else:
            return jsonify({
                "error": "Failed to set resolution",
                "message": "Camera may not support this resolution"
            }), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting resolution")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_mode/video', methods=['POST'])
def switch_to_video_mode():
    """Switch camera to video/stream mode"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = camera_controller.switch_to_video_mode()
    
    if success:
        return jsonify({
            "message": "Switched to video mode",
            "mode": "video",
            "resolution": camera_controller.get_current_resolution()
        })
    else:
        return jsonify({"error": "Failed to switch to video mode"}), 500


@camera_bp.route('/camera_mode/still', methods=['POST'])
def switch_to_still_mode():
    """Switch camera to still capture mode"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = camera_controller.switch_to_still_mode()
    
    if success:
        return jsonify({
            "message": "Switched to still mode",
            "mode": "still",
            "resolution": camera_controller.get_current_resolution()
        })
    else:
        return jsonify({"error": "Failed to switch to still mode"}), 500


@camera_bp.route('/camera_info', methods=['GET'])
def get_camera_info():
    """Get comprehensive camera information"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    return jsonify(camera_controller.get_camera_info())


# ======= WHITE BALANCE AND COLOR CORRECTION ENDPOINTS ===========

@camera_bp.route('/camera_awb/auto_detect', methods=['POST'])
def auto_detect_white_balance():
    """Detect and apply optimal white balance automatically"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        from camera.camera_utils import detect_and_fix_blue_tint, auto_white_balance_by_environment
        
        # Detectar y corregir tinte azul
        blue_tint_fixed = detect_and_fix_blue_tint(camera_controller)
        
        # Si no había tinte azul, usar detección de entorno
        if not blue_tint_fixed:
            recommended_awb = auto_white_balance_by_environment()
            success = camera_controller.update_control("AwbMode", recommended_awb)
            
            if success:
                awb_names = {0: "Auto", 1: "Incandescent", 5: "Daylight"}
                return jsonify({
                    "message": f"White balance set to {awb_names.get(recommended_awb, 'Unknown')}",
                    "awb_mode": recommended_awb,
                    "blue_tint_detected": False
                })
            else:
                return jsonify({"error": "Failed to set white balance"}), 500
        else:
            return jsonify({
                "message": "Blue tint detected and corrected",
                "awb_mode": camera_controller.get_control_value("AwbMode"),
                "blue_tint_detected": True
            })
            
    except Exception as e:
        logger.exception("[Camera] Error in auto white balance detection")
        return jsonify({"error": str(e)}), 500


@camera_bp.route('/camera_awb/<int:mode>', methods=['POST'])
def set_white_balance_mode(mode):
    """Set specific white balance mode"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    from camera.camera_utils import CameraControlLimits
    limits = CameraControlLimits()
    
    if mode not in limits.AWB_MODES:
        return jsonify({
            "error": "Invalid AWB mode",
            "available_modes": limits.AWB_MODES
        }), 400
    
    success = camera_controller.update_control("AwbMode", mode)
    
    if success:
        mode_name = limits.AWB_MODES[mode]
        return jsonify({
            "message": f"White balance set to {mode_name}",
            "awb_mode": mode,
            "mode_name": mode_name
        })
    else:
        return jsonify({"error": "Failed to set white balance mode"}), 500


@camera_bp.route('/camera_preset/balanced', methods=['POST'])
def apply_balanced_preset():
    """Apply a balanced preset that avoids color issues"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        from camera.camera_utils import create_balanced_preset
        
        balanced_controls = create_balanced_preset()
        success = camera_controller.update_multiple_controls(balanced_controls)
        
        if success:
            return jsonify({
                "message": "Balanced preset applied successfully",
                "applied_controls": balanced_controls,
                "current_controls": camera_controller.get_current_controls()
            })
        else:
            return jsonify({"error": "Failed to apply balanced preset"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error applying balanced preset")
        return jsonify({"error": str(e)}), 500


# ======= SERVER-SIDE ZOOM AND PAN (ROI) ENDPOINTS =======

@camera_bp.route('/camera_roi', methods=['GET'])
def get_camera_roi():
    """Get current Region of Interest (server-side zoom/pan)"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    roi = camera_controller.get_roi()
    x, y, width, height = roi
    
    # Calculate zoom level (1.0 = no zoom, 2.0 = 2x zoom, etc.)
    zoom_level = 1.0 / min(width, height)
    
    return jsonify({
        "roi": {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        },
        "zoom_level": round(zoom_level, 2),
        "is_zoomed": width < 1.0 or height < 1.0
    })


@camera_bp.route('/camera_roi', methods=['POST'])
def set_camera_roi():
    """Set Region of Interest (server-side zoom/pan)"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        x = float(data.get('x', 0.0))
        y = float(data.get('y', 0.0))
        width = float(data.get('width', 1.0))
        height = float(data.get('height', 1.0))
        
        success = camera_controller.set_roi(x, y, width, height)
        
        if success:
            new_roi = camera_controller.get_roi()
            zoom_level = 1.0 / min(new_roi[2], new_roi[3])
            
            return jsonify({
                "message": "ROI updated successfully",
                "roi": {
                    "x": new_roi[0],
                    "y": new_roi[1], 
                    "width": new_roi[2],
                    "height": new_roi[3]
                },
                "zoom_level": round(zoom_level, 2)
            })
        else:
            return jsonify({"error": "Failed to set ROI"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error setting ROI")
        return jsonify({"error": str(e)}), 400


@camera_bp.route('/camera_zoom', methods=['POST'])
def camera_zoom():
    """Apply zoom to current ROI"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        zoom_factor = float(data.get('zoom_factor', 1.0))
        center_x = float(data.get('center_x', 0.5))
        center_y = float(data.get('center_y', 0.5))
        
        success = camera_controller.zoom_roi(zoom_factor, center_x, center_y)
        
        if success:
            new_roi = camera_controller.get_roi()
            zoom_level = 1.0 / min(new_roi[2], new_roi[3])
            
            return jsonify({
                "message": f"Zoom applied: {zoom_factor}x",
                "roi": {
                    "x": new_roi[0],
                    "y": new_roi[1],
                    "width": new_roi[2], 
                    "height": new_roi[3]
                },
                "zoom_level": round(zoom_level, 2)
            })
        else:
            return jsonify({"error": "Failed to apply zoom"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error applying zoom")
        return jsonify({"error": str(e)}), 400


@camera_bp.route('/camera_pan', methods=['POST'])
def camera_pan():
    """Pan (move) current ROI"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    try:
        data = request.get_json()
        delta_x = float(data.get('delta_x', 0.0))
        delta_y = float(data.get('delta_y', 0.0))
        
        success = camera_controller.pan_roi(delta_x, delta_y)
        
        if success:
            new_roi = camera_controller.get_roi()
            
            return jsonify({
                "message": f"Pan applied: ({delta_x:.2f}, {delta_y:.2f})",
                "roi": {
                    "x": new_roi[0],
                    "y": new_roi[1],
                    "width": new_roi[2],
                    "height": new_roi[3]
                }
            })
        else:
            return jsonify({"error": "Failed to pan"}), 500
            
    except Exception as e:
        logger.exception("[Camera] Error panning")
        return jsonify({"error": str(e)}), 400


@camera_bp.route('/camera_roi/reset', methods=['POST'])
def reset_camera_roi():
    """Reset ROI to full frame (no zoom/pan)"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = camera_controller.reset_roi()
    
    if success:
        return jsonify({
            "message": "ROI reset to full frame",
            "roi": {
                "x": 0.0,
                "y": 0.0,
                "width": 1.0,
                "height": 1.0
            },
            "zoom_level": 1.0
        })
    else:
        return jsonify({"error": "Failed to reset ROI"}), 500
