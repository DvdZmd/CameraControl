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
async def esp32_status():
    controller = get_ble_controller()
    status = await controller.get_status()
    return jsonify(status), 200


@esp32_bp.route("/connect", methods=["POST"])
async def esp32_connect():
    controller = get_ble_controller()
    try:
        result = await controller.connect()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/disconnect", methods=["POST"])
async def esp32_disconnect():
    controller = get_ble_controller()
    try:
        result = await controller.disconnect()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/command", methods=["POST"])
async def esp32_command():
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
        result = await controller.send_command(command)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/center", methods=["POST"])
async def esp32_center():
    controller = get_ble_controller()
    try:
        result = await controller.center()
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/speed", methods=["POST"])
async def esp32_speed():
    controller = get_ble_controller()
    data = request.get_json(silent=True) or {}

    mode = data.get("mode")
    if mode is None:
        return jsonify({"ok": False, "error": "mode es requerido"}), 400

    try:
        mode = int(mode)
        result = await controller.set_speed(mode)
        return jsonify(result), 200
    except ValueError as ex:
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@esp32_bp.route("/move", methods=["POST"])
async def esp32_move():
    controller = get_ble_controller()
    data = request.get_json(silent=True) or {}

    direction = (data.get("direction") or "").strip().lower()
    action = (data.get("action") or "start").strip().lower()

    if action not in {"start", "stop"}:
        return jsonify({"ok": False, "error": "action debe ser 'start' o 'stop'"}), 400

    if action == "stop":
        try:
            result = await controller.send_command("STOP")
            return jsonify(result), 200
        except Exception as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500

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
        result = await controller.send_command(command)
        return jsonify(result), 200
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500