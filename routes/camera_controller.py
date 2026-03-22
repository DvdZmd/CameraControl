from flask import Blueprint, Response, request, jsonify, render_template, send_file
from camera.rpicam_z import rpicamz
import time
import io

camera_controller_bp = Blueprint(
    'camera_controller', 
    __name__, 
    url_prefix="/api/camera")

@camera_controller_bp.route('/')
def index():
    """
    Serve the main camera control page.

    This Flask route handles ``GET /api/camera/`` and returns the HTML user
    interface for camera control.

    Returns:
        A rendered ``index.html`` response.

    Example:
        curl http://localhost:5000/api/camera/
    """
    return render_template('index.html')

@camera_controller_bp.route('/reset', methods=['POST'])
def reset_camera():
    """
    Reset camera settings to their default values.

    This Flask route handles ``POST /api/camera/reset`` and triggers camera
    reconfiguration through Picamera2. The request performs direct hardware
    access and may block while the stream restarts.

    Returns:
        A JSON response indicating success.

    Example:
        curl -X POST http://localhost:5000/api/camera/reset
    """
    rpicamz.reset_to_defaults()
    return jsonify({"status": "success", "message": "Camera reset to defaults"})

@camera_controller_bp.route('/apply_preset', methods=['POST'])
def apply_preset():
    """
    Apply a named camera preset.

    This Flask route handles ``POST /api/camera/apply_preset`` and forwards the
    request to the active camera controller. Applying a preset writes camera
    controls to Picamera2 and may fail if the preset name is unknown.

    Returns:
        A JSON response with ``status: success`` when the preset is applied, or
        an error payload with HTTP 404 when the preset does not exist.

    Example:
        curl -X POST http://localhost:5000/api/camera/apply_preset \
             -H "Content-Type: application/json" \
             -d '{"preset": "LUNAR_PHOTOGRAPHY"}'
    """
    preset_name = request.json.get('preset') # Example: 'LUNAR_PHOTOGRAPHY'
    if rpicamz.apply_preset(preset_name):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Preset not found"}), 404

@camera_controller_bp.route('/take_photo_custom')
def take_photo_custom():
    """
    Capture a still image at the requested resolution.

    This Flask route handles ``GET /api/camera/take_photo_custom``. It
    temporarily reconfigures the camera, captures one JPEG image, and returns it
    as a downloadable file. The request performs direct camera hardware access
    and may block for the duration of the capture.

    Returns:
        A JPEG file response named ``custom_snap_<width>x<height>.jpg``.

    Example:
        curl "http://localhost:5000/api/camera/take_photo_custom?w=1920&h=1080" \
             --output custom.jpg
    """
    # Receive width and height through URL parameters (?w=1920&h=1080)
    w = request.args.get('w', default=1280, type=int)
    h = request.args.get('h', default=720, type=int)
    
    image_binary = rpicamz.take_custom_photo(w, h)
    
    return send_file(
        io.BytesIO(image_binary),
        mimetype='image/jpeg',
        as_attachment=True,
        download_name=f"custom_snap_{w}x{h}.jpg"
    )

def generate_frames():
    """
    Yield multipart JPEG frames for HTTP streaming.

    The generator reads frames from Picamera2 in an infinite loop and is meant
    to back a multipart MJPEG Flask response. Each iteration performs direct
    camera access and sleeps for approximately 30 milliseconds to target about
    30 frames per second.

    Returns:
        An iterator of multipart JPEG byte chunks.
    """
    while True:
        frame = rpicamz.get_jpeg_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03) # ~30 FPS

@camera_controller_bp.route('/video_feed')
def video_feed():
    """
    Stream live camera frames as an MJPEG response.

    This Flask route handles ``GET /api/camera/video_feed`` and keeps the HTTP
    connection open while frames are generated from the active camera stream.

    Returns:
        A multipart HTTP response with content type
        ``multipart/x-mixed-replace``.

    Example:
        curl http://localhost:5000/api/camera/video_feed
    """
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_controller_bp.route('/camera_status')
def camera_status():
    """
    Return cached camera capabilities and current stream state.

    This Flask route handles ``GET /api/camera/camera_status`` and exposes
    information about the active camera without triggering a new hardware probe.

    Returns:
        A JSON response containing sensor limits, autofocus support, and the
        current stream resolution.

    Example:
        curl http://localhost:5000/api/camera/camera_status
    """
    return jsonify(rpicamz.get_capabilities())


@camera_controller_bp.route('/update_settings', methods=['POST'])
def update_settings():
    """
    Update camera stream settings and runtime controls.

    This Flask route handles ``POST /api/camera/update_settings``. Depending on
    the payload, it may restart the camera stream, adjust live Picamera2
    controls, or start and stop a timelapse background thread. Exposure time is
    interpreted in microseconds, rotation in degrees, and timelapse intervals in
    seconds.

    Returns:
        A JSON response indicating success after all requested updates are
        applied.

    Example:
        curl -X POST http://localhost:5000/api/camera/update_settings \
             -H "Content-Type: application/json" \
             -d '{"width": 1280, "height": 720, "rotation": 90, "Brightness": 0.1}'
    """
    data = request.json
    
    # Resolution change
    if 'width' in data and 'height' in data:
        rpicamz.set_resolution(int(data['width']), int(data['height']))

    # Rotation handling
    if 'rotation' in data:
        rpicamz.set_rotation(int(data['rotation']))

    # Timelapse handling
    if 'timelapse' in data:
        if data['timelapse'] == 'start':
            interval = int(data.get('interval', 5))
            # Optional: pass the desired resolution for timelapse
            tw = data.get('t_width') 
            th = data.get('t_height')
            rpicamz.start_timelapse(interval, tw, th)
        else:
            rpicamz.stop_timelapse() 
    
    # Update controls (Brightness, Contrast, Saturation, Sharpness, AfMode)
    for param in ['Brightness', 'Contrast', 'Saturation', 'Sharpness', 'AfMode', 'LensPosition', 'ExposureTime', 'AnalogueGain']:
        if param in data:
            rpicamz.update_control(param, data[param])
            
    return jsonify({"status": "success"})
