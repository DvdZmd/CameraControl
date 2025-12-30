from flask import Blueprint, request, jsonify
from camera.picam import camera_controller
from camera.camera_utils import (
    CameraPresets, CameraControlLimits, validate_control_value,
    apply_preset, get_focus_distance_estimate,
    calculate_optimal_exposure, generate_focus_steps, get_control_info
)
from logs.logging_config import logger

camera_controls_bp = Blueprint('camera_controls', __name__)


# ======= CAMERA CONTROLS ENDPOINTS ===========

@camera_controls_bp.route('/camera_controls', methods=['GET'])
def get_camera_controls():
    """Get available camera controls and their current values"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    return jsonify({
        "available_controls": camera_controller.get_available_controls(),
        "current_controls": camera_controller.get_current_controls(),
        "control_info": get_control_info()
    })


@camera_controls_bp.route('/camera_control/<control_name>', methods=['POST'])
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


@camera_controls_bp.route('/camera_controls', methods=['POST'])
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


@camera_controls_bp.route('/camera_reset', methods=['POST'])
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


# ======= PRESETS ENDPOINTS ===========

@camera_controls_bp.route('/camera_presets', methods=['GET'])
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


@camera_controls_bp.route('/camera_preset/<preset_name>', methods=['POST'])
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


@camera_controls_bp.route('/camera_preset/balanced', methods=['POST'])
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


# ======= FOCUS CONTROL ENDPOINTS ===========

@camera_controls_bp.route('/camera_focus/manual', methods=['POST'])
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


@camera_controls_bp.route('/camera_focus/auto', methods=['POST'])
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


@camera_controls_bp.route('/camera_focus/sweep', methods=['POST'])
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


# ======= EXPOSURE CONTROL ENDPOINTS ===========

@camera_controls_bp.route('/camera_exposure/auto', methods=['POST'])
def set_auto_exposure():
    """Set automatic exposure"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    success = camera_controller.update_control("ExposureTime", None)
    if success:
        return jsonify({"message": "Automatic exposure enabled"})
    else:
        return jsonify({"error": "Failed to set automatic exposure"}), 500


@camera_controls_bp.route('/camera_exposure/manual', methods=['POST'])
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


@camera_controls_bp.route('/camera_exposure/scene', methods=['POST'])
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
