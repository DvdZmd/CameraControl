import os
import time
import cv2
from datetime import datetime
from threading import Event
from flask import Blueprint, Response, request, send_file, jsonify, render_template
from camera.picam import camera_controller
from camera.timelapse import start_timelapse, stop_timelapse, get_timelapse_config
from logs.logging_config import logger

camera_basic_bp = Blueprint('camera_basic', __name__)

# Shared state variables
camera_stream_enabled = True
rotation_angle = 0
timelapse_thread = None
timelapse_stop_event = Event()


@camera_basic_bp.route('/')
def index():
    """Serve the main camera control interface"""
    return render_template('index.html')


@camera_basic_bp.route('/toggle_camera', methods=['POST'])
def toggle_camera():
    global camera_stream_enabled
    camera_stream_enabled = not camera_stream_enabled
    return jsonify({
        "enabled": camera_stream_enabled,
        "message": "Camera turned " + ("on" if camera_stream_enabled else "off")
    })


@camera_basic_bp.route('/set_rotation', methods=['POST'])
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


def generate_frames():
    """Generate frames for video stream"""
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


@camera_basic_bp.route('/video_feed')
def video_feed():
    """MJPEG video stream endpoint"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_basic_bp.route('/camera_status', methods=['GET'])
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


@camera_basic_bp.route('/camera_info', methods=['GET'])
def get_camera_info():
    """Get comprehensive camera information"""
    if not camera_controller.picam2:
        return jsonify({"error": "Camera not available"}), 503
    
    return jsonify(camera_controller.get_camera_info())


@camera_basic_bp.route('/capture_image', methods=['GET'])
def capture_image():
    """Capture image using CameraController with automatic mode switching"""
    if not camera_controller.picam2:
        return jsonify({
            "error": "Camera not available", 
            "message": "Camera is not connected or not properly configured"
        }), 503

    try:
        from config import AVAILABLE_RESOLUTIONS
        
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


@camera_basic_bp.route('/timelapse_status', methods=['GET'])
def timelapse_status():
    """Get current timelapse configuration and status"""
    return jsonify(get_timelapse_config())


@camera_basic_bp.route('/timelapse', methods=['POST'])
def handle_timelapse():
    """Start or stop timelapse capture"""
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
