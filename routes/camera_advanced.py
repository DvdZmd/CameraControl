from flask import Blueprint, request, jsonify
from config import AVAILABLE_RESOLUTIONS
from camera.picam import camera_controller
from camera.camera_utils import CameraControlLimits
from logs.logging_config import logger

camera_advanced_bp = Blueprint('camera_advanced', __name__)


# ======= RESOLUTION AND MODE CONTROL ENDPOINTS ===========

@camera_advanced_bp.route('/camera_resolution', methods=['GET'])
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


@camera_advanced_bp.route('/camera_resolution', methods=['POST'])
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


@camera_advanced_bp.route('/set_stream_resolution', methods=['POST'])
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


@camera_advanced_bp.route('/camera_mode/video', methods=['POST'])
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


@camera_advanced_bp.route('/camera_mode/still', methods=['POST'])
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


# ======= WHITE BALANCE AND COLOR CORRECTION ENDPOINTS ===========

@camera_advanced_bp.route('/camera_awb/auto_detect', methods=['POST'])
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


@camera_advanced_bp.route('/camera_awb/<int:mode>', methods=['POST'])
def set_white_balance_mode(mode):
    """Set specific white balance mode"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
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


# ======= SERVER-SIDE ZOOM AND PAN (ROI) ENDPOINTS =======

@camera_advanced_bp.route('/camera_roi', methods=['GET'])
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


@camera_advanced_bp.route('/camera_roi', methods=['POST'])
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


@camera_advanced_bp.route('/camera_zoom', methods=['POST'])
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


@camera_advanced_bp.route('/camera_pan', methods=['POST'])
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


@camera_advanced_bp.route('/camera_roi/reset', methods=['POST'])
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
