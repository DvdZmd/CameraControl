from flask import Blueprint, current_app, jsonify, request


timelapse_bp = Blueprint("timelapse", __name__, url_prefix="/api/timelapse")


def get_timelapse_service():
    service = current_app.config.get("TIMELAPSE_SERVICE")
    if service is None:
        raise RuntimeError("Servicio de timelapse no configurado")
    return service


def _positive_int(data, name, minimum=1):
    value = data.get(name)
    if isinstance(value, bool):
        raise ValueError(f"{name} debe ser un entero")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} debe ser un entero") from error
    if parsed < minimum:
        raise ValueError(f"{name} debe ser mayor o igual a {minimum}")
    return parsed


@timelapse_bp.route("/status", methods=["GET"])
def timelapse_status():
    return jsonify(get_timelapse_service().status())


@timelapse_bp.route("/config", methods=["PUT"])
def update_timelapse_config():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Se requiere un objeto JSON"}), 400
    try:
        allowed = {
            "interval_seconds", "width", "height", "auto_resume",
            "light_enabled", "light_intensity",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"Campos no soportados: {', '.join(unknown)}")
        interval = _positive_int(data, "interval_seconds", 2)
        width = _positive_int(data, "width")
        height = _positive_int(data, "height")
        auto_resume = data.get("auto_resume")
        if not isinstance(auto_resume, bool):
            raise ValueError("auto_resume debe ser booleano")
        light_enabled = data.get("light_enabled", False)
        if not isinstance(light_enabled, bool):
            raise ValueError("light_enabled debe ser booleano")
        light_intensity = data.get("light_intensity", 100)
        if isinstance(light_intensity, bool):
            raise ValueError("light_intensity debe ser un entero")
        try:
            light_intensity = int(light_intensity)
        except (TypeError, ValueError) as error:
            raise ValueError("light_intensity debe ser un entero") from error
        if light_intensity < 1:
            raise ValueError("light_intensity debe estar entre 1 y 100")
        if light_intensity > 100:
            raise ValueError("light_intensity debe estar entre 1 y 100")
        status = get_timelapse_service().configure(
            interval_seconds=interval,
            width=width,
            height=height,
            auto_resume=auto_resume,
            light_enabled=light_enabled,
            light_intensity=light_intensity,
        )
        return jsonify(status)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 409


@timelapse_bp.route("/start", methods=["POST"])
def start_timelapse():
    try:
        return jsonify(get_timelapse_service().start())
    except Exception as error:
        return jsonify({"error": str(error)}), 503


@timelapse_bp.route("/stop", methods=["POST"])
def stop_timelapse():
    try:
        return jsonify(get_timelapse_service().stop())
    except Exception as error:
        return jsonify({"error": str(error)}), 503
