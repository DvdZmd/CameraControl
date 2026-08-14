from flask import Blueprint, current_app, jsonify, request
import logging
from database.models import Esp32Settings, db
import re

esp32_bp = Blueprint(
    "camera",
    __name__,
    url_prefix="/api/esp32"
)
pan_tilt_bp = Blueprint(
    "pan_tilt",
    __name__,
    url_prefix="/api/esp32",
)
lighting_bp = Blueprint(
    "lighting",
    __name__,
    url_prefix="/api/esp32",
)
module_logger = logging.getLogger(__name__)

def get_ble_controller():
    """
    Retrieve the shared ESP32 BLE controller from Flask configuration.

    Returns:
        The configured BLE controller instance.

    Raises:
        RuntimeError: If the application was not initialized with a BLE
            controller.
    """
    controller = current_app.config.get("BLE_CAMERA_CONTROLLER")
    if controller is None:
        raise RuntimeError("BLE controller no configurado en Flask")
    return controller


SIMPLE_COMMANDS = {
    "PAN_LEFT",
    "PAN_RIGHT",
    "TILT_UP",
    "TILT_DOWN",
    "CENTER",
    "STOP",
    "LIGHT_ON",
    "LIGHT_OFF",
}
SET_SPEED_PATTERN = re.compile(r"SET_SPEED:([0-4])")
SET_ABS_PATTERN = re.compile(r"SET_ABS:(\d+),(\d+)")
SET_LIGHT_PATTERN = re.compile(r"SET_LIGHT:(\d{1,3})")
SERVO_PULSE_MIN_US = 500
SERVO_PULSE_MAX_US = 2400
SERVO_ANGLE_MIN_DEG = 0
SERVO_ANGLE_MAX_DEG = 180
DEFAULT_SETTINGS_ID = 1


def _pulse_to_angle_deg(pulse):
    pulse_range = SERVO_PULSE_MAX_US - SERVO_PULSE_MIN_US
    angle_range = SERVO_ANGLE_MAX_DEG - SERVO_ANGLE_MIN_DEG
    return round(
        SERVO_ANGLE_MIN_DEG
        + ((pulse - SERVO_PULSE_MIN_US) * angle_range / pulse_range),
        1,
    )


def _servo_position_payload(pan, tilt):
    return {
        "pan": {
            "pulse_us": pan,
            "angle_deg": _pulse_to_angle_deg(pan),
        },
        "tilt": {
            "pulse_us": tilt,
            "angle_deg": _pulse_to_angle_deg(tilt),
        },
    }


def _json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"ok": False, "error": "Se requiere un objeto JSON"}), 400)
    return data, None


def _validate_command(raw_command):
    if not isinstance(raw_command, str) or not raw_command.strip():
        return None, "command debe ser un string no vacío"

    command = raw_command.strip().upper()
    if command in SIMPLE_COMMANDS:
        return command, None

    if SET_SPEED_PATTERN.fullmatch(command):
        return command, None

    light_match = SET_LIGHT_PATTERN.fullmatch(command)
    if light_match:
        intensity = int(light_match.group(1))
        if 0 <= intensity <= 100:
            return command, None
        return None, "la intensidad de luz debe estar entre 0 y 100"

    absolute_match = SET_ABS_PATTERN.fullmatch(command)
    if absolute_match:
        pan, tilt = (int(value) for value in absolute_match.groups())
        if all(SERVO_PULSE_MIN_US <= value <= SERVO_PULSE_MAX_US for value in (pan, tilt)):
            return command, None
        return None, f"pan y tilt deben estar entre {SERVO_PULSE_MIN_US} y {SERVO_PULSE_MAX_US} us"

    return None, f"Comando no permitido o formato inválido: {command}"


def _command_feature(command):
    if command in {"LIGHT_ON", "LIGHT_OFF"} or SET_LIGHT_PATTERN.fullmatch(command):
        return "lighting"
    return "pan_tilt"


def _feature_enabled(name):
    return bool(current_app.config.get("FEATURES", {}).get(name))


def _database_ready():
    try:
        return db.engine is not None
    except Exception:
        return False


def _saved_esp32_settings():
    if not _database_ready():
        return None
    return db.session.get(Esp32Settings, DEFAULT_SETTINGS_ID)


def _saved_position_payload(settings=None):
    settings = settings or _saved_esp32_settings()
    if (
        settings is None
        or settings.custom_pan_pulse is None
        or settings.custom_tilt_pulse is None
    ):
        return None
    return {
        "pan": settings.custom_pan_pulse,
        "tilt": settings.custom_tilt_pulse,
    }


def _saved_position_details_payload(settings=None):
    saved_position = _saved_position_payload(settings)
    if saved_position is None:
        return None
    return _servo_position_payload(saved_position["pan"], saved_position["tilt"])


def _saved_speed_mode(settings=None):
    settings = settings or _saved_esp32_settings()
    if settings is None or settings.speed_mode is None:
        return None
    return settings.speed_mode


def _saved_light_payload(settings=None):
    settings = settings or _saved_esp32_settings()
    if settings is None:
        return {"light_on": False, "intensity": 100}
    return {
        "light_on": bool(settings.light_on),
        "intensity": settings.light_intensity if settings.light_intensity is not None else 100,
    }


def _persist_light_settings(*, light_on, intensity):
    settings = db.session.get(Esp32Settings, DEFAULT_SETTINGS_ID)
    if settings is None:
        settings = Esp32Settings(id=DEFAULT_SETTINGS_ID)
        db.session.add(settings)
    settings.light_on = light_on
    settings.light_intensity = intensity
    db.session.commit()


def _apply_saved_light(controller):
    saved = _saved_light_payload()
    applied_intensity = saved["intensity"] if saved["light_on"] else 0
    controller.send_command_sync(f"SET_LIGHT:{applied_intensity}")
    last_state = getattr(controller, "last_state", None)
    if isinstance(last_state, dict):
        last_state["L"] = str(applied_intensity)
    return saved


def ensure_esp32_settings_schema(logger=None):
    if not _database_ready():
        return

    try:
        with db.engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(esp32_settings)")
            }
            if "speed_mode" not in columns:
                connection.exec_driver_sql("ALTER TABLE esp32_settings ADD COLUMN speed_mode INTEGER")
            if "light_on" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE esp32_settings ADD COLUMN light_on BOOLEAN NOT NULL DEFAULT 0"
                )
            if "light_intensity" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE esp32_settings ADD COLUMN light_intensity INTEGER NOT NULL DEFAULT 100"
                )
    except Exception:
        active_logger = logger or module_logger
        active_logger.exception("No se pudo actualizar el esquema de configuración ESP32")


def _parse_servo_pulse(value, name):
    try:
        pulse = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} no está disponible en la telemetría ESP32")

    if not SERVO_PULSE_MIN_US <= pulse <= SERVO_PULSE_MAX_US:
        raise ValueError(
            f"{name} debe estar entre {SERVO_PULSE_MIN_US} y {SERVO_PULSE_MAX_US} us"
        )
    return pulse


def _current_servo_position(controller):
    status = controller.get_status_sync()
    last_state = status.get("last_state") or {}
    pan = _parse_servo_pulse(last_state.get("P"), "pan")
    tilt = _parse_servo_pulse(last_state.get("T"), "tilt")
    return pan, tilt


def _current_position_payload_from_status(status):
    last_state = status.get("last_state") or {}
    try:
        pan = _parse_servo_pulse(last_state.get("P"), "pan")
        tilt = _parse_servo_pulse(last_state.get("T"), "tilt")
    except ValueError:
        return None
    return _servo_position_payload(pan, tilt)


def _cache_speed_mode(controller, mode):
    last_state = getattr(controller, "last_state", None)
    if isinstance(last_state, dict):
        last_state["S"] = str(mode)


@esp32_bp.route("/status", methods=["GET"])
def esp32_status():
    """
    Return the current ESP32 BLE connection status.

    This Flask route handles ``GET /api/esp32/status`` and returns cached BLE
    state without issuing a movement command.

    Returns:
        A JSON response containing connection metadata and the latest status
        notification received from the ESP32.

    Example:
        curl http://localhost:5000/api/esp32/status
    """
    controller = get_ble_controller()
    status = controller.get_status_sync()
    settings = _saved_esp32_settings()
    if _feature_enabled("pan_tilt"):
        status["saved_position"] = _saved_position_payload(settings)
        status["saved_position_details"] = _saved_position_details_payload(settings)
        status["saved_speed_mode"] = _saved_speed_mode(settings)
        status["current_position"] = _current_position_payload_from_status(status)
    if _feature_enabled("lighting"):
        status["saved_light"] = _saved_light_payload(settings)
    return jsonify(status), 200


@esp32_bp.route("/connect", methods=["POST"])
def esp32_connect():
    """
    Connect to the ESP32 over BLE.

    This Flask route handles ``POST /api/esp32/connect``. The request can block
    while the server scans for the device, establishes a BLE session, and
    subscribes to notifications.

    Returns:
        A JSON response describing the BLE connection state.

    Example:
        curl -X POST http://localhost:5000/api/esp32/connect
    """
    controller = get_ble_controller()
    try:
        result = controller.connect_sync()
        if _feature_enabled("lighting"):
            saved_light = _apply_saved_light(controller)
            result["saved_light"] = saved_light
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/disconnect", methods=["POST"])
def esp32_disconnect():
    """
    Disconnect from the ESP32 BLE device.

    This Flask route handles ``POST /api/esp32/disconnect`` and releases the
    active BLE client if one is connected.

    Returns:
        A JSON response describing the disconnected state.

    Example:
        curl -X POST http://localhost:5000/api/esp32/disconnect
    """
    controller = get_ble_controller()
    try:
        result = controller.disconnect_sync()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/command", methods=["POST"])
def esp32_command():
    """
    Send a validated command to the ESP32 over BLE.

    This Flask route handles ``POST /api/esp32/command``. It accepts a JSON
    body with a ``command`` string, validates the command against an allowlist,
    and forwards it to the BLE controller. The request may block on BLE
    transport and external-device latency.

    Returns:
        A JSON response with the command execution result, or an error payload
        for invalid or failed commands.

    Example:
        curl -X POST http://localhost:5000/api/esp32/command \
             -H "Content-Type: application/json" \
             -d '{"command": "PAN_LEFT"}'
    """
    controller = get_ble_controller()
    data, error_response = _json_object()
    if error_response:
        return error_response

    command, validation_error = _validate_command(data.get("command"))
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400
    required_feature = _command_feature(command)
    if not _feature_enabled(required_feature):
        return jsonify({
            "ok": False,
            "error": f"La capacidad {required_feature} está deshabilitada",
        }), 403

    try:
        result = controller.send_command_sync(command)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@pan_tilt_bp.route("/center", methods=["POST"])
def esp32_center():
    """
    Send the centering command to the ESP32.

    This Flask route handles ``POST /api/esp32/center`` and delegates the
    operation to the BLE controller.

    Returns:
        A JSON response describing the command result.

    Example:
        curl -X POST http://localhost:5000/api/esp32/center
    """
    controller = get_ble_controller()
    try:
        result = controller.center_sync()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@lighting_bp.route("/light", methods=["POST"])
def esp32_light():
    """Set GPIO21 LED-strip intensity through ESP32 PWM."""
    data, error_response = _json_object()
    if error_response:
        return error_response

    has_intensity = "intensity" in data
    has_on = "on" in data
    if has_intensity == has_on:
        return jsonify({
            "ok": False,
            "error": "Debe enviarse intensity o on, pero no ambos",
        }), 400

    if has_intensity:
        intensity = data.get("intensity")
        if isinstance(intensity, bool) or not isinstance(intensity, int):
            return jsonify({"ok": False, "error": "intensity debe ser un entero"}), 400
        if intensity < 0 or intensity > 100:
            return jsonify({
                "ok": False,
                "error": "intensity debe estar entre 0 y 100",
            }), 400
        light_on = intensity > 0
        saved_intensity = intensity if light_on else _saved_light_payload()["intensity"]
        command = f"SET_LIGHT:{intensity}"
    else:
        light_on = data.get("on")
        if not isinstance(light_on, bool):
            return jsonify({"ok": False, "error": "on debe ser booleano"}), 400
        saved = _saved_light_payload()
        saved_intensity = saved["intensity"]
        intensity = saved_intensity if light_on else 0
        if not light_on:
            command = "LIGHT_OFF"
        elif intensity == 100:
            command = "LIGHT_ON"
        else:
            command = f"SET_LIGHT:{intensity}"

    controller = get_ble_controller()
    try:
        result = controller.send_command_sync(command)
        result["light_on"] = intensity > 0
        result["intensity"] = intensity
        last_state = getattr(controller, "last_state", None)
        if isinstance(last_state, dict):
            last_state["L"] = str(intensity)
        if _database_ready():
            _persist_light_settings(light_on=light_on, intensity=saved_intensity)
        result["saved_intensity"] = saved_intensity
        return jsonify(result), 200
    except Exception as ex:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(ex)}), 500


@pan_tilt_bp.route("/position/current", methods=["POST"])
def esp32_save_current_position():
    """
    Persist the current ESP32 pan/tilt position from cached telemetry.

    The route does not move the servos. It requires valid ``P`` and ``T`` values
    in the latest ESP32 notification and stores them as the custom return
    position.
    """
    controller = get_ble_controller()
    if not _database_ready():
        return jsonify({"ok": False, "error": "Base de datos no disponible"}), 503

    try:
        pan, tilt = _current_servo_position(controller)
        settings = db.session.get(Esp32Settings, DEFAULT_SETTINGS_ID)
        if settings is None:
            settings = Esp32Settings(id=DEFAULT_SETTINGS_ID)
            db.session.add(settings)

        settings.custom_pan_pulse = pan
        settings.custom_tilt_pulse = tilt
        db.session.commit()
        return jsonify({
            "ok": True,
            "saved_position": _saved_position_payload(settings),
            "saved_position_details": _saved_position_details_payload(settings),
        }), 200
    except ValueError as ex:
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(ex)}), 500


@pan_tilt_bp.route("/position/return", methods=["POST"])
def esp32_return_to_saved_position():
    """
    Move the ESP32 head to the persisted custom pan/tilt position.

    The route validates persisted pulse values before sending ``SET_ABS`` to the
    firmware.
    """
    controller = get_ble_controller()
    saved_position = _saved_position_payload()
    if saved_position is None:
        return jsonify({"ok": False, "error": "No hay una posición configurada"}), 404

    pan = saved_position["pan"]
    tilt = saved_position["tilt"]
    if not all(SERVO_PULSE_MIN_US <= value <= SERVO_PULSE_MAX_US for value in (pan, tilt)):
        return jsonify({"ok": False, "error": "La posición guardada es inválida"}), 400

    try:
        command = f"SET_ABS:{pan},{tilt}"
        result = controller.send_command_sync(command)
        result["saved_position"] = saved_position
        result["saved_position_details"] = _servo_position_payload(pan, tilt)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@pan_tilt_bp.route("/speed", methods=["POST"])
def esp32_speed():
    """
    Set the ESP32 movement speed preset.

    This Flask route handles ``POST /api/esp32/speed``. The JSON body must
    contain a ``mode`` field in the inclusive range 0 to 4, which is forwarded
    as a BLE command to the external device.

    Returns:
        A JSON response describing the command result, or an error payload if
        the mode is missing or invalid.

    Example:
        curl -X POST http://localhost:5000/api/esp32/speed \
             -H "Content-Type: application/json" \
             -d '{"mode": 2}'
    """
    controller = get_ble_controller()
    data, error_response = _json_object()
    if error_response:
        return error_response

    mode = data.get("mode")
    if mode is None:
        return jsonify({"ok": False, "error": "mode es requerido"}), 400

    try:
        if isinstance(mode, bool):
            raise ValueError("mode debe ser un entero entre 0 y 4")
        mode = int(mode)
        if str(mode) != str(data.get("mode")).strip() or not 0 <= mode <= 4:
            raise ValueError("mode debe ser un entero entre 0 y 4")
        result = controller.set_speed_sync(mode)
        _cache_speed_mode(controller, mode)
        if _database_ready():
            settings = db.session.get(Esp32Settings, DEFAULT_SETTINGS_ID)
            if settings is None:
                settings = Esp32Settings(id=DEFAULT_SETTINGS_ID)
                db.session.add(settings)
            settings.speed_mode = mode
            db.session.commit()
            result["saved_speed_mode"] = mode
        result["current_speed_mode"] = mode
        return jsonify(result), 200
    except ValueError as ex:
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(ex)}), 500


@pan_tilt_bp.route("/move", methods=["POST"])
def esp32_move():
    """
    Move the ESP32-controlled head in one cardinal direction.

    This Flask route handles ``POST /api/esp32/move``. The JSON body must
    include ``direction`` with one of ``left``, ``right``, ``up``, or ``down``.
    The route translates the value into a BLE command and sends it to the
    external device, which may introduce hardware latency.

    Returns:
        A JSON response describing the command result, or an error payload for
        invalid directions.

    Example:
        curl -X POST http://localhost:5000/api/esp32/move \
             -H "Content-Type: application/json" \
             -d '{"direction": "left"}'
    """
    controller = get_ble_controller()
    data, error_response = _json_object()
    if error_response:
        return error_response

    raw_direction = data.get("direction")
    if not isinstance(raw_direction, str):
        return jsonify({"ok": False, "error": "direction debe ser un string"}), 400
    direction = raw_direction.strip().lower()

    direction_map = {
        "left": "PAN_LEFT",
        "right": "PAN_RIGHT",
        "up": "TILT_UP",
        "down": "TILT_DOWN",
    }

    command = direction_map.get(direction)
    if not command:
        return jsonify({"ok": False, "error": "direction inválida"}), 400

    try:
        # We send the command and the ESP32 will execute it only once
        result = controller.send_command_sync(command)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500
