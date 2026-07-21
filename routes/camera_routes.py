from flask import Blueprint, Response, request, jsonify, render_template, send_file
from rpicam_z.rpicam_z import CAMERA_IMPORT_ERROR, UnavailableCamera, rpicam_z
import time
import io


MAX_DIMENSION_PX = 10000
ALLOWED_ROTATIONS = {0, 90, 180, 270}
CONTROL_RANGES = {
    'Brightness': (-1.0, 1.0),
    'Contrast': (0.0, 32.0),
    'Saturation': (0.0, 32.0),
    'Sharpness': (0.0, 16.0),
    'AfMode': (0, 2),
    'LensPosition': (0.0, 32.0),
    'ExposureTime': (1, 1_000_000_000),
    'AnalogueGain': (1.0, 16.0),
}
SETTINGS_FIELDS = {
    'width', 'height', 'rotation', 'timelapse', 'interval', 't_width', 't_height',
    *CONTROL_RANGES,
}

camera_bp = Blueprint(
    'camera_controller', 
    __name__, 
    url_prefix="/api/camera")


if CAMERA_IMPORT_ERROR is None:
    rpicamz = rpicam_z()
else:
    rpicamz = UnavailableCamera(CAMERA_IMPORT_ERROR)


def _camera_unavailable_response(error):
    return jsonify({
        "status": "error",
        "message": str(error),
    }), 503


def _error_response(message, status=400):
    return jsonify({"status": "error", "message": message}), status


def _parse_int(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} debe ser un entero")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} debe ser un entero") from error
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} debe ser un entero")
    return parsed


def _validate_dimensions(width, height):
    width = _parse_int(width, "width")
    height = _parse_int(height, "height")
    if not (1 <= width <= MAX_DIMENSION_PX and 1 <= height <= MAX_DIMENSION_PX):
        raise ValueError(f"width y height deben estar entre 1 y {MAX_DIMENSION_PX} píxeles")
    return width, height


def _validate_control(name, value):
    minimum, maximum = CONTROL_RANGES[name]
    try:
        parsed = int(value) if name in {'AfMode', 'ExposureTime'} else float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} debe ser numérico") from error
    if isinstance(value, bool) or not minimum <= parsed <= maximum:
        raise ValueError(f"{name} debe estar entre {minimum} y {maximum}")
    return parsed

@camera_bp.route('/')
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

@camera_bp.route('/reset', methods=['POST'])
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
    try:
        rpicamz.reset_to_defaults()
    except RuntimeError as error:
        return _camera_unavailable_response(error)
    return jsonify({"status": "success", "message": "Camera reset to defaults"})

@camera_bp.route('/apply_preset', methods=['POST'])
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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response("Se requiere un objeto JSON")
    preset_name = data.get('preset')
    if not isinstance(preset_name, str) or not preset_name.strip():
        return _error_response("preset debe ser un string no vacío")
    preset_name = preset_name.strip()
    try:
        applied = rpicamz.apply_preset(preset_name)
    except RuntimeError as error:
        return _camera_unavailable_response(error)

    if applied:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Preset not found"}), 404

@camera_bp.route('/take_photo_custom')
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
    try:
        w, h = _validate_dimensions(
            request.args.get('w', default=1280),
            request.args.get('h', default=720),
        )
    except ValueError as error:
        return _error_response(str(error))
    
    try:
        image_binary = rpicamz.take_custom_photo(w, h)
    except RuntimeError as error:
        return _camera_unavailable_response(error)
    
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
        try:
            packet = rpicamz.get_frame_packet()
        except RuntimeError as error:
            print(f"Error occurred while generating frames: {error}")
            return

        if packet:
            if isinstance(packet, dict):
                jpeg_bytes = packet.get("jpeg_bytes")
            else:
                jpeg_bytes = getattr(packet, "jpeg_bytes", None)

            if jpeg_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
        time.sleep(0.03)  # ~30 FPS

def generate_frames_sync():
    """
    Yield multipart JPEG frames with per-frame timestamp metadata.

    The generator reads frame packets from ``rpicamz.get_frame_packet()`` and
    emits a multipart MJPEG stream where each part includes frame identifier and
    nanosecond timestamps in custom headers.

    Returns:
        An iterator of multipart JPEG byte chunks with metadata headers.
    """
    while True:
        try:
            packet = rpicamz.get_frame_packet()
        except RuntimeError as error:
            print(f"Error occurred while generating sync frames: {error}")
            return

        if packet:
            if isinstance(packet, dict):
                frame_id = packet.get("frame_id")
                jpeg_bytes = packet.get("jpeg_bytes")
                captured_wall_time_ns = packet.get("captured_wall_time_ns")
                captured_monotonic_ns = packet.get("captured_monotonic_ns")
            else:
                frame_id = getattr(packet, "frame_id", None)
                jpeg_bytes = getattr(packet, "jpeg_bytes", None)
                captured_wall_time_ns = getattr(packet, "captured_wall_time_ns", None)
                captured_monotonic_ns = getattr(packet, "captured_monotonic_ns", None)

            if jpeg_bytes:
                headers = (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    + f'X-Frame-Id: {frame_id}\r\n'.encode('ascii')
                    + f'X-Timestamp-Wall-Ns: {captured_wall_time_ns}\r\n'.encode('ascii')
                    + f'X-Timestamp-Mono-Ns: {captured_monotonic_ns}\r\n\r\n'.encode('ascii')
                )
                yield headers + jpeg_bytes + b'\r\n'
        time.sleep(0.03) # ~30 FPS

@camera_bp.route('/video_feed')
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

@camera_bp.route('/video_feed_sync')
def video_feed_sync():
    """
    Stream live camera frames with per-frame timing metadata.

    This Flask route handles ``GET /api/camera/video_feed_sync`` and keeps the
    HTTP connection open while frames and timestamp headers are generated from
    the active camera stream.

    Returns:
        A multipart HTTP response with content type
        ``multipart/x-mixed-replace``.

    Example:
        curl http://localhost:5000/api/camera/video_feed_sync
    """
    return Response(generate_frames_sync(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_bp.route('/camera_status')
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
    try:
        return jsonify(rpicamz.get_capabilities())
    except RuntimeError as error:
        return _camera_unavailable_response(error)


@camera_bp.route('/update_settings', methods=['POST'])
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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response("Se requiere un objeto JSON")
    if not data:
        return _error_response("El objeto JSON no puede estar vacío")

    try:
        unknown_fields = sorted(set(data) - SETTINGS_FIELDS)
        if unknown_fields:
            raise ValueError(f"Campos no soportados: {', '.join(unknown_fields)}")

        validated = {}

        has_width = 'width' in data
        has_height = 'height' in data
        if has_width != has_height:
            raise ValueError("width y height deben enviarse juntos")
        if has_width:
            validated['resolution'] = _validate_dimensions(data['width'], data['height'])

        if 'rotation' in data:
            rotation = _parse_int(data['rotation'], 'rotation')
            if rotation not in ALLOWED_ROTATIONS:
                raise ValueError("rotation debe ser 0, 90, 180 o 270")
            validated['rotation'] = rotation

        if 'timelapse' in data:
            action = data['timelapse']
            if action not in {'start', 'stop'}:
                raise ValueError("timelapse debe ser 'start' o 'stop'")
            if action == 'start':
                interval = _parse_int(data.get('interval', 5), 'interval')
                if interval <= 0:
                    raise ValueError("interval debe ser mayor que cero segundos")
                # Optional: pass the desired resolution for timelapse
                tw = data.get('t_width')
                th = data.get('t_height')
                if (tw is None) != (th is None):
                    raise ValueError("t_width y t_height deben enviarse juntos")
                if tw is not None:
                    tw, th = _validate_dimensions(tw, th)
                validated['timelapse'] = ('start', interval, tw, th)
            else:
                validated['timelapse'] = ('stop',)
        elif any(field in data for field in {'interval', 't_width', 't_height'}):
            raise ValueError("interval, t_width y t_height requieren timelapse='start'")

        controls = {}
        for param in CONTROL_RANGES:
            if param in data:
                controls[param] = _validate_control(param, data[param])
        validated['controls'] = controls
    except ValueError as error:
        return _error_response(str(error))

    try:
        if 'resolution' in validated:
            rpicamz.set_resolution(*validated['resolution'])

        if 'rotation' in validated:
            rpicamz.set_rotation(validated['rotation'])

        if 'timelapse' in validated:
            timelapse = validated['timelapse']
            if timelapse[0] == 'start':
                rpicamz.start_timelapse(*timelapse[1:])
            else:
                rpicamz.stop_timelapse()

        image_params = {'Brightness', 'Contrast', 'Saturation', 'Sharpness', 'AfMode', 'LensPosition'}
        for param, value in validated['controls'].items():
            rpicamz.update_control(param, value)
            if param in image_params:
                # Add a small delay to allow image processing settings to apply before the next frame is requested.
                # This helps prevent the UI from appearing to "freeze" for these specific controls.
                time.sleep(0.05)
    except RuntimeError as error:
        return _camera_unavailable_response(error)
            
    return jsonify({"status": "success"})
