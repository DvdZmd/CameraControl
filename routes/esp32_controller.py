from flask import Blueprint, current_app, jsonify, request

esp32_bp = Blueprint(
    "camera",
    __name__,
    url_prefix="/api/esp32"
)

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
    data = request.get_json(silent=True) or {}

    command = (data.get("command") or "").strip().upper()
    if not command:
        return jsonify({"ok": False, "error": "command es requerido"}), 400

    allowed_commands = {
        "PAN_LEFT",
        "PAN_RIGHT",
        "TILT_UP",
        "TILT_DOWN",
        "CENTER",
        "STOP",
    }

    if not (command in allowed_commands or command.startswith("SET_SPEED:") or command.startswith("SET_ABS:")):
        return jsonify({"ok": False, "error": f"Comando no permitido: {command}"}), 400

    try:
        result = controller.send_command_sync(command)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/center", methods=["POST"])
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


@esp32_bp.route("/speed", methods=["POST"])
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
    data = request.get_json(silent=True) or {}

    mode = data.get("mode")
    if mode is None:
        return jsonify({"ok": False, "error": "mode es requerido"}), 400

    try:
        mode = int(mode)
        result = controller.set_speed_sync(mode)
        return jsonify(result), 200
    except ValueError as ex:
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/move", methods=["POST"])
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
    data = request.get_json(silent=True) or {}
    direction = (data.get("direction") or "").strip().lower()

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
