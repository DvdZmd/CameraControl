from flask import Blueprint, current_app, jsonify

tuya_bp = Blueprint(
    "tuya",
    __name__,
    url_prefix="/api/tuya"
)

def get_tuya_controller():
    """
    Recupera el controlador de Tuya desde la configuración de Flask.
    """
    controller = current_app.config.get("TUYA_CONTROLLER")
    if controller is None:
        raise RuntimeError("Controlador Tuya no configurado en Flask")
    return controller

@tuya_bp.route("/status", methods=["GET"])
def get_tuya_status():
    """
    Obtiene el estado actual del dispositivo Tuya.
    """
    controller = get_tuya_controller()
    status = controller.get_status()
    if status["ok"]:
        return jsonify(status), 200
    else:
        return jsonify(status), 500

@tuya_bp.route("/on", methods=["POST"])
def turn_on_plug():
    """
    Enciende el enchufe Tuya.
    """
    controller = get_tuya_controller()
    result = controller.set_status(True)
    if result["ok"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@tuya_bp.route("/off", methods=["POST"])
def turn_off_plug():
    """
    Apaga el enchufe Tuya.
    """
    controller = get_tuya_controller()
    result = controller.set_status(False)
    if result["ok"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 500