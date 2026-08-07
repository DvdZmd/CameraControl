from flask import Blueprint, Response, current_app, request, jsonify, render_template, send_file
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from database.models import CameraSettings, db
from rpicam_z.rpicam_z import CAMERA_IMPORT_ERROR, UnavailableCamera, rpicam_z
import time
import io


MAX_DIMENSION_PX = 10000
ALLOWED_ROTATIONS = {0, 90, 180, 270}
SAFE_PIPELINE_ROTATIONS = {0, 180}
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
BOOLEAN_CONTROLS = {'AeEnable'}
PERSISTABLE_CONTROLS = {
    *CONTROL_RANGES,
    *BOOLEAN_CONTROLS,
    'AwbMode',
    'DigitalGain',
}
SETTINGS_FIELDS = {
    'width', 'height', 'rotation', 'timelapse', 'interval', 't_width', 't_height',
    *CONTROL_RANGES,
    *BOOLEAN_CONTROLS,
}


def _photo_download_name():
    timezone_name = current_app.config.get(
        "APP_TIMEZONE", "America/Argentina/Buenos_Aires"
    )
    try:
        captured_at = datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        captured_at = datetime.now().astimezone()
    return f"{captured_at.strftime('%Y_%m_%d_%H-%M-%S')}.jpg"

camera_bp = Blueprint(
    'camera_controller', 
    __name__, 
    url_prefix="/api/camera")


stream_enabled = False
camera_closed_by_user = False
module_logger = logging.getLogger(__name__)


def _unavailable_camera(error):
    try:
        return UnavailableCamera(error)
    except Exception:
        return _LocalUnavailableCamera(error)


class _LocalUnavailableCamera:
    def __init__(self, error):
        self.error = error

    def get_capabilities(self):
        return {
            "available": False,
            "error": str(self.error),
        }

    def __getattr__(self, name):
        if isinstance(self.error, BaseException):
            raise RuntimeError(f"La cámara no está disponible: {self.error}") from self.error
        raise RuntimeError(f"La cámara no está disponible: {self.error}")


def _create_camera_controller():
    if CAMERA_IMPORT_ERROR is not None:
        return _unavailable_camera(CAMERA_IMPORT_ERROR)

    try:
        return rpicam_z()
    except Exception as error:
        return _unavailable_camera(error)


rpicamz = _create_camera_controller()


def _camera_unavailable_response(error):
    return jsonify({
        "status": "error",
        "available": False,
        "stream_enabled": False,
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
    if name in BOOLEAN_CONTROLS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {'true', 'false'}:
            return value.lower() == 'true'
        raise ValueError(f"{name} debe ser booleano")

    minimum, maximum = CONTROL_RANGES[name]
    try:
        parsed = int(value) if name in {'AfMode', 'ExposureTime'} else float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} debe ser numérico") from error
    if isinstance(value, bool) or not minimum <= parsed <= maximum:
        raise ValueError(f"{name} debe estar entre {minimum} y {maximum}")
    return parsed


def _camera_properties():
    picam2 = getattr(rpicamz, 'picam2', None)
    properties = getattr(picam2, 'camera_properties', None)
    return properties if isinstance(properties, dict) else {}


def _is_camera_available():
    try:
        capabilities = rpicamz.get_capabilities()
    except Exception:
        return False
    return capabilities.get("available") is not False


def _camera_unavailable_from_capabilities(capabilities):
    message = capabilities.get("error", "cámara no disponible")
    return _camera_unavailable_response(message)


def _camera_model():
    properties = _camera_properties()
    return properties.get('Model') or properties.get('SensorModel')


def _camera_key(capabilities):
    model = _camera_model() or 'unknown'
    max_width = capabilities.get('max_width')
    max_height = capabilities.get('max_height')
    af_supported = capabilities.get('af_supported')
    return f"{model}:{max_width}x{max_height}:af={int(bool(af_supported))}"


def _supported_camera_controls():
    picam2 = getattr(rpicamz, 'picam2', None)
    available_controls = getattr(picam2, 'camera_controls', None)
    if isinstance(available_controls, dict):
        controls = set(available_controls)
    else:
        controls = set(PERSISTABLE_CONTROLS)

    if not getattr(rpicamz, 'af_supported', False):
        controls.discard('AfMode')
        controls.discard('LensPosition')
    return controls


def _rotation_state(capabilities=None):
    if capabilities is None:
        capabilities = {}

    requested = capabilities.get('current_rotation', getattr(rpicamz, 'current_rotation', 0))
    pipeline = capabilities.get('pipeline_rotation', getattr(rpicamz, 'pipeline_rotation', None))
    if pipeline is None:
        pipeline = requested if requested in SAFE_PIPELINE_ROTATIONS else 0

    display = capabilities.get('display_rotation', getattr(rpicamz, 'display_rotation', None))
    if display is None:
        display = (requested - pipeline) % 360

    return {
        'rotation': requested,
        'pipeline_rotation': pipeline,
        'display_rotation': display,
    }


def _set_camera_rotation(rotation):
    set_rotation = getattr(rpicamz, 'set_rotation', None)
    if not callable(set_rotation):
        return False

    capabilities = rpicamz.get_capabilities()
    supported_pipeline_rotations = set(
        capabilities.get('supported_pipeline_rotations') or SAFE_PIPELINE_ROTATIONS
    )

    if 'supported_pipeline_rotations' in capabilities or rotation in supported_pipeline_rotations:
        return set_rotation(rotation) is not False

    # Compatibilidad con rpicam-z antiguo: no enviar 90/270 al pipeline.
    pipeline_rotation = rotation if rotation in supported_pipeline_rotations else 0
    if set_rotation(pipeline_rotation) is False:
        return False
    rpicamz.current_rotation = rotation
    rpicamz.pipeline_rotation = pipeline_rotation
    rpicamz.display_rotation = (rotation - rpicamz.pipeline_rotation) % 360
    return True


def _current_camera_state(capabilities=None, overrides=None):
    if capabilities is None:
        capabilities = rpicamz.get_capabilities()
    overrides = overrides or {}

    controls = getattr(rpicamz, 'controls', {})
    if not isinstance(controls, dict):
        controls = {}

    supported_controls = _supported_camera_controls()
    persisted_controls = {
        name: value
        for name, value in controls.items()
        if name in PERSISTABLE_CONTROLS and name in supported_controls
    }

    rotation = _rotation_state(capabilities)
    rotation.update({key: value for key, value in overrides.items() if key in rotation})

    return {
        'camera_key': _camera_key(capabilities),
        'camera_model': _camera_model(),
        'max_width': capabilities.get('max_width'),
        'max_height': capabilities.get('max_height'),
        'af_supported': capabilities.get('af_supported'),
        'width': overrides.get('width') or capabilities.get('current_width') or getattr(rpicamz, 'current_width', 1280),
        'height': overrides.get('height') or capabilities.get('current_height') or getattr(rpicamz, 'current_height', 720),
        'rotation': rotation['rotation'],
        'pipeline_rotation': rotation['pipeline_rotation'],
        'display_rotation': rotation['display_rotation'],
        'controls': persisted_controls,
    }


def ensure_camera_settings_schema(logger=None):
    if not _database_ready():
        return

    try:
        with db.engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(camera_settings)")
            }
            migrations = {
                "pipeline_rotation": "ALTER TABLE camera_settings ADD COLUMN pipeline_rotation INTEGER NOT NULL DEFAULT 0",
                "display_rotation": "ALTER TABLE camera_settings ADD COLUMN display_rotation INTEGER NOT NULL DEFAULT 0",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.exec_driver_sql(statement)
    except Exception:
        active_logger = logger or module_logger
        active_logger.exception("No se pudo actualizar el esquema de configuración de cámara")


def _save_current_camera_settings(overrides=None):
    if not _database_ready():
        return

    try:
        state = _current_camera_state(overrides=overrides)
        settings = CameraSettings.query.filter_by(camera_key=state['camera_key']).first()
        if settings is None:
            settings = CameraSettings(camera_key=state['camera_key'])
            db.session.add(settings)

        settings.camera_model = state['camera_model']
        settings.max_width = state['max_width']
        settings.max_height = state['max_height']
        settings.af_supported = state['af_supported']
        settings.width = state['width']
        settings.height = state['height']
        settings.rotation = state['rotation']
        settings.pipeline_rotation = state['pipeline_rotation']
        settings.display_rotation = state['display_rotation']
        settings.controls = state['controls']
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        module_logger.exception("No se pudo persistir la configuración de cámara")


def _saved_camera_settings(capabilities=None):
    if not _database_ready():
        return None

    if capabilities is None:
        capabilities = rpicamz.get_capabilities()
    return CameraSettings.query.filter_by(camera_key=_camera_key(capabilities)).first()


def _apply_control(name, value):
    result = rpicamz.update_control(name, value)
    if result is False:
        module_logger.warning("Control de cámara no aplicado: %s=%r", name, value)
    return result


def _database_ready():
    try:
        db.engine
    except RuntimeError:
        return False
    return True


def apply_saved_camera_settings(logger=None):
    logger = logger or module_logger
    if not _is_camera_available():
        logger.warning("No se aplicó configuración persistida: cámara no disponible")
        return False
    if not callable(getattr(rpicamz, 'get_capabilities', None)):
        logger.warning("No se aplicó configuración persistida: controlador de cámara incompleto")
        return False

    try:
        capabilities = rpicamz.get_capabilities()
        saved = _saved_camera_settings(capabilities)
        if saved is None:
            return False

        max_width = capabilities.get('max_width') or MAX_DIMENSION_PX
        max_height = capabilities.get('max_height') or MAX_DIMENSION_PX
        width = min(saved.width, max_width)
        height = min(saved.height, max_height)
        if width != capabilities.get('current_width') or height != capabilities.get('current_height'):
            rpicamz.set_resolution(width, height)

        if saved.rotation in ALLOWED_ROTATIONS and not _set_camera_rotation(saved.rotation):
            logger.warning("Rotación persistida no aplicada: %s", saved.rotation)

        supported_controls = _supported_camera_controls()
        controls = saved.controls or {}
        for name, value in controls.items():
            if name in supported_controls and name in PERSISTABLE_CONTROLS:
                _apply_control(name, value)

        logger.info("Configuración de cámara persistida aplicada: %s", saved.camera_key)
        return True
    except Exception as error:
        logger.warning("No se aplicó configuración persistida de cámara: %s", error)
        return False

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
    _save_current_camera_settings()
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
        _save_current_camera_settings()
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
        A JPEG response named with its local capture timestamp.

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
        download_name=_photo_download_name()
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
    while stream_enabled:
        try:
            packet = rpicamz.get_frame_packet()
        except RuntimeError as error:
            module_logger.error("Error generando frames: %s", error)
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
    while stream_enabled:
        try:
            packet = rpicamz.get_frame_packet()
        except RuntimeError as error:
            module_logger.error("Error generando frames sincronizados: %s", error)
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
    if not stream_enabled:
        return _error_response("Streaming de cámara apagado", 409)
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
    if not stream_enabled:
        return _error_response("Streaming de cámara apagado", 409)
    return Response(generate_frames_sync(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_bp.route('/stream/start', methods=['POST'])
def start_stream():
    """
    Enable MJPEG streaming and retry camera initialization if it was unavailable.
    """
    global rpicamz, stream_enabled, camera_closed_by_user

    if camera_closed_by_user or not _is_camera_available():
        rpicamz = _create_camera_controller()
        camera_closed_by_user = False

    if not _is_camera_available():
        stream_enabled = False
        try:
            capabilities = rpicamz.get_capabilities()
            error = capabilities.get("error", "cámara no disponible")
        except Exception as runtime_error:
            error = runtime_error
        return _camera_unavailable_response(error)

    stream_enabled = True
    apply_saved_camera_settings(module_logger)
    timelapse_service = current_app.config.get("TIMELAPSE_SERVICE")
    if timelapse_service is not None:
        timelapse_service.resume_if_needed()
    return jsonify({"status": "success", "stream_enabled": True})


@camera_bp.route('/stream/stop', methods=['POST'])
def stop_stream():
    """
    Disable only MJPEG frame delivery, keeping the camera available to captures.
    """
    global stream_enabled, camera_closed_by_user

    stream_enabled = False
    camera_closed_by_user = False

    return jsonify({"status": "success", "stream_enabled": False})


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
        capabilities = rpicamz.get_capabilities()
        if capabilities.get("available") is False:
            return _camera_unavailable_from_capabilities(capabilities)
        state = _current_camera_state(capabilities)
        capabilities.update({
            "available": True,
            "stream_enabled": stream_enabled,
            "camera_key": state['camera_key'],
            "camera_model": state['camera_model'],
            "current_rotation": state['rotation'],
            "pipeline_rotation": state['pipeline_rotation'],
            "display_rotation": state['display_rotation'],
            "controls": state['controls'],
            "supported_controls": sorted(_supported_camera_controls()),
        })
        return jsonify(capabilities)
    except Exception as error:
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
        for param in (*CONTROL_RANGES, *BOOLEAN_CONTROLS):
            if param in data:
                controls[param] = _validate_control(param, data[param])
        validated['controls'] = controls
    except ValueError as error:
        return _error_response(str(error))

    try:
        if 'resolution' in validated:
            rpicamz.set_resolution(*validated['resolution'])

        if 'rotation' in validated:
            if not _set_camera_rotation(validated['rotation']):
                raise RuntimeError("No se pudo aplicar la rotación de cámara")

        if 'timelapse' in validated:
            timelapse = validated['timelapse']
            timelapse_service = current_app.config.get("TIMELAPSE_SERVICE")
            if timelapse_service is not None and timelapse[0] == 'start':
                current_status = timelapse_service.status()
                timelapse_service.configure(
                    interval_seconds=timelapse[1],
                    width=timelapse[2] or current_status['width'],
                    height=timelapse[3] or current_status['height'],
                    auto_resume=current_status['auto_resume'],
                    light_enabled=current_status['light_enabled'],
                    light_intensity=current_status['light_intensity'],
                    folder_name=current_status['folder_name'],
                )
                timelapse_service.start()
            elif timelapse_service is not None:
                timelapse_service.stop()
            elif timelapse[0] == 'start':
                rpicamz.start_timelapse(*timelapse[1:])
            else:
                rpicamz.stop_timelapse()

        image_params = {'Brightness', 'Contrast', 'Saturation', 'Sharpness', 'AfMode', 'LensPosition', 'AeEnable'}
        for param, value in validated['controls'].items():
            _apply_control(param, value)
            if param in image_params:
                # Add a small delay to allow image processing settings to apply before the next frame is requested.
                # This helps prevent the UI from appearing to "freeze" for these specific controls.
                time.sleep(0.05)
    except RuntimeError as error:
        return _camera_unavailable_response(error)

    if 'resolution' in validated or 'rotation' in validated or validated['controls']:
        overrides = {}
        if 'resolution' in validated:
            overrides['width'], overrides['height'] = validated['resolution']
        _save_current_camera_settings(overrides)

    rotation = _rotation_state(rpicamz.get_capabilities())
    return jsonify({
        "status": "success",
        "current_rotation": rotation['rotation'],
        "pipeline_rotation": rotation['pipeline_rotation'],
        "display_rotation": rotation['display_rotation'],
    })
