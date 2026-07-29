from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from database.models import TuyaDevice, db
from tuya.tuya_controller import normalize_tuya_status

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


def _database_ready():
    try:
        return db.engine is not None
    except Exception:
        return False


def _serialize_device(device, status_result=None):
    payload = {
        "id": device.id,
        "name": device.name,
        "tuya_name": device.tuya_name,
        "device_id": device.device_id,
        "switch_code": device.switch_code,
        "enabled": device.enabled,
    }

    if isinstance(status_result, dict):
        payload["status_ok"] = bool(status_result.get("ok"))
        if status_result.get("ok"):
            status = status_result.get("status") or {}
            normalized = (
                status_result
                if "electrical" in status_result
                else normalize_tuya_status(status, device.switch_code)
            )
            payload["status"] = status
            payload["is_on"] = normalized["switch"]["is_on"]
            payload["switch"] = normalized["switch"]
            payload["electrical"] = normalized["electrical"]
            payload["safety"] = normalized["safety"]
            payload["settings"] = normalized["settings"]
            payload["capabilities"] = normalized["capabilities"]
            payload["cached"] = bool(status_result.get("cached"))
            payload["fetched_at"] = status_result.get("fetched_at")
        else:
            payload["error"] = status_result.get("error", "Error desconocido")

    return payload


def _remote_tuya_name(details):
    if not isinstance(details, dict) or not details.get("ok"):
        return None

    name = details.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _refresh_tuya_device_details(controller, device):
    get_details = getattr(controller, "get_device_details", None)
    if not callable(get_details):
        return None

    result = get_details(device.device_id)
    remote_name = _remote_tuya_name(result)
    if remote_name and remote_name != device.tuya_name:
        device.tuya_name = remote_name
        db.session.commit()
    return result


def _validate_device_payload(data):
    if not isinstance(data, dict):
        return None, "Se requiere un objeto JSON"

    name = data.get("name")
    device_id = data.get("device_id")
    switch_code = data.get("switch_code", "switch_1")

    if not isinstance(name, str) or not name.strip():
        return None, "name debe ser un string no vacío"
    if not isinstance(device_id, str) or not device_id.strip():
        return None, "device_id debe ser un string no vacío"
    if not isinstance(switch_code, str) or not switch_code.strip():
        return None, "switch_code debe ser un string no vacío"

    name = name.strip()
    device_id = device_id.strip()
    switch_code = switch_code.strip()

    if len(name) > 120:
        return None, "name no puede superar 120 caracteres"
    if len(device_id) > 255:
        return None, "device_id no puede superar 255 caracteres"
    if len(switch_code) > 80:
        return None, "switch_code no puede superar 80 caracteres"

    return {
        "name": name,
        "device_id": device_id,
        "switch_code": switch_code,
    }, None


def _validate_device_update_payload(data):
    if not isinstance(data, dict):
        return None, "Se requiere un objeto JSON"

    updates = {}
    if "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "name debe ser un string no vacío"
        name = name.strip()
        if len(name) > 120:
            return None, "name no puede superar 120 caracteres"
        updates["name"] = name

    if not updates:
        return None, "No hay cambios válidos para aplicar"
    return updates, None


def _device_or_404(device_pk):
    if not _database_ready():
        return None, (jsonify({"ok": False, "error": "Base de datos no disponible"}), 503)

    device = db.session.get(TuyaDevice, device_pk)
    if device is None or not device.enabled:
        return None, (jsonify({"ok": False, "error": "Dispositivo Tuya no encontrado"}), 404)
    return device, None


def ensure_tuya_legacy_device(config, logger=None):
    if not _database_ready() or not getattr(config, "device_id", ""):
        return

    try:
        existing = TuyaDevice.query.filter_by(device_id=config.device_id).first()
        if existing is not None:
            return

        db.session.add(TuyaDevice(
            name="Enchufe Tuya",
            tuya_name=None,
            device_id=config.device_id,
            switch_code="switch_1",
        ))
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        active_logger = logger or current_app.logger
        active_logger.exception("No se pudo inicializar el dispositivo Tuya legado")


def ensure_tuya_devices_schema(logger=None):
    if not _database_ready():
        return

    try:
        with db.engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(tuya_device)")
            }
            if "tuya_name" not in columns:
                connection.exec_driver_sql("ALTER TABLE tuya_device ADD COLUMN tuya_name VARCHAR(255)")
    except Exception:
        active_logger = logger or current_app.logger
        active_logger.exception("No se pudo actualizar el esquema de dispositivos Tuya")


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


@tuya_bp.route("/devices", methods=["GET"])
def list_tuya_devices():
    """
    Lista los dispositivos Tuya configurados localmente en la aplicación.

    Este endpoint no consulta Tuya Cloud. El cupo gratuito de la IoT Platform es
    limitado y las lecturas remotas deben quedar detrás de acciones explícitas
    del usuario.
    """
    if not _database_ready():
        return jsonify({"ok": False, "error": "Base de datos no disponible"}), 503

    devices = TuyaDevice.query.filter_by(enabled=True).order_by(TuyaDevice.name.asc()).all()
    payload = [_serialize_device(device) for device in devices]

    return jsonify({"ok": True, "devices": payload}), 200


@tuya_bp.route("/devices", methods=["POST"])
def add_tuya_device():
    """
    Agrega un dispositivo Tuya ya dado de alta en la IoT Platform.
    """
    if not _database_ready():
        return jsonify({"ok": False, "error": "Base de datos no disponible"}), 503

    payload, validation_error = _validate_device_payload(request.get_json(silent=True))
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    device = TuyaDevice(**payload)
    db.session.add(device)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "error": "El device_id ya está configurado"}), 409
    except Exception as error:
        db.session.rollback()
        current_app.logger.exception("Error agregando dispositivo Tuya")
        return jsonify({"ok": False, "error": str(error)}), 500

    return jsonify({"ok": True, "device": _serialize_device(device)}), 201


@tuya_bp.route("/devices/<int:device_pk>", methods=["PATCH"])
def update_tuya_device(device_pk):
    """
    Actualiza metadatos locales del dispositivo Tuya.
    """
    device, error_response = _device_or_404(device_pk)
    if error_response:
        return error_response

    updates, validation_error = _validate_device_update_payload(request.get_json(silent=True))
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    try:
        for key, value in updates.items():
            setattr(device, key, value)
        db.session.commit()
        return jsonify({"ok": True, "device": _serialize_device(device)}), 200
    except Exception as error:
        db.session.rollback()
        current_app.logger.exception("Error actualizando dispositivo Tuya")
        return jsonify({"ok": False, "error": str(error)}), 500


@tuya_bp.route("/devices/<int:device_pk>/details", methods=["POST"])
def refresh_tuya_device_details(device_pk):
    """
    Refresca metadatos remotos del dispositivo desde Tuya.
    """
    device, error_response = _device_or_404(device_pk)
    if error_response:
        return error_response

    controller = get_tuya_controller()
    try:
        result = _refresh_tuya_device_details(controller, device)
        if not isinstance(result, dict):
            return jsonify({"ok": False, "error": "El controlador no soporta detalle de dispositivo"}), 501
        if not result.get("ok"):
            return _tuya_response(result)
        return jsonify({"ok": True, "device": _serialize_device(device)}), 200
    except Exception as error:
        db.session.rollback()
        current_app.logger.exception("Error refrescando detalle Tuya")
        return jsonify({"ok": False, "error": str(error)}), 503


@tuya_bp.route("/devices/<int:device_pk>/status", methods=["POST"])
def set_tuya_device_status(device_pk):
    """
    Enciende o apaga un dispositivo Tuya persistido.
    """
    device, error_response = _device_or_404(device_pk)
    if error_response:
        return error_response

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("on"), bool):
        return jsonify({"ok": False, "error": "on debe ser booleano"}), 400

    controller = get_tuya_controller()
    try:
        result = controller.set_status(
            data["on"],
            device_id=device.device_id,
            switch_code=device.switch_code,
        )
        return _tuya_response(result)
    except Exception as error:
        current_app.logger.exception("Error modificando dispositivo Tuya")
        return jsonify({"ok": False, "error": str(error)}), 503


@tuya_bp.route("/devices/<int:device_pk>/status", methods=["GET"])
def refresh_tuya_device_status(device_pk):
    """
    Consulta el estado remoto del dispositivo desde Tuya bajo demanda.
    """
    device, error_response = _device_or_404(device_pk)
    if error_response:
        return error_response

    controller = get_tuya_controller()
    try:
        result = controller.get_status(
            device.device_id,
            switch_code=device.switch_code,
            force_refresh=True,
        )
        if not result.get("ok"):
            return _tuya_response(result)
        return jsonify({"ok": True, "device": _serialize_device(device, result)}), 200
    except Exception as error:
        current_app.logger.exception("Error consultando estado Tuya")
        return jsonify({"ok": False, "error": str(error)}), 503
