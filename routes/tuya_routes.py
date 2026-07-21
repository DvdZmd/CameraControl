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


def _tuya_response(result):
    if not isinstance(result, dict):
        return jsonify({"ok": False, "error": "Respuesta inválida del controlador Tuya"}), 502
    if result.get("ok"):
        return jsonify(result), 200
    return jsonify(result), 503

@tuya_bp.route("/status", methods=["GET"])
def get_tuya_status():
    """
    Obtiene el estado actual del dispositivo Tuya.
    """
    controller = get_tuya_controller()
    try:
        return _tuya_response(controller.get_status())
    except Exception as error:
        current_app.logger.exception("Error consultando estado Tuya")
        return jsonify({"ok": False, "error": str(error)}), 503

@tuya_bp.route("/on", methods=["POST"])
def turn_on_plug():
    """
    Enciende el enchufe Tuya.
    """
    controller = get_tuya_controller()
    try:
        return _tuya_response(controller.set_status(True))
    except Exception as error:
        current_app.logger.exception("Error encendiendo dispositivo Tuya")
        return jsonify({"ok": False, "error": str(error)}), 503

@tuya_bp.route("/off", methods=["POST"])
def turn_off_plug():
    """
    Apaga el enchufe Tuya.
    """
    controller = get_tuya_controller()
    try:
        return _tuya_response(controller.set_status(False))
    except Exception as error:
        current_app.logger.exception("Error apagando dispositivo Tuya")
        return jsonify({"ok": False, "error": str(error)}), 503
