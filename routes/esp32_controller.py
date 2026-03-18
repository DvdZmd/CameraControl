from flask import Blueprint, current_app, jsonify, request

esp32_bp = Blueprint(
    "camera",
    __name__,
    url_prefix="/api/esp32"
)

def get_ble_controller():
    controller = current_app.config.get("BLE_CAMERA_CONTROLLER")
    if controller is None:
        raise RuntimeError("BLE controller no configurado en Flask")
    return controller


@esp32_bp.route("/status", methods=["GET"])
def esp32_status():
    controller = get_ble_controller()
    status = controller.get_status_sync()
    return jsonify(status), 200


@esp32_bp.route("/connect", methods=["POST"])
def esp32_connect():
    controller = get_ble_controller()
    try:
        result = controller.connect_sync()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/disconnect", methods=["POST"])
def esp32_disconnect():
    controller = get_ble_controller()
    try:
        result = controller.disconnect_sync()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/command", methods=["POST"])
def esp32_command():
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
    controller = get_ble_controller()
    try:
        result = controller.center_sync()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/speed", methods=["POST"])
def esp32_speed():
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
        # Enviamos el comando y el ESP32 lo ejecutará una sola vez
        result = controller.send_command_sync(command)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500