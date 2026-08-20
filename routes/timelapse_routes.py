import math
import os
import tempfile
import zipfile

from flask import Blueprint, after_this_request, current_app, jsonify, request, send_file


timelapse_bp = Blueprint("timelapse", __name__, url_prefix="/api/timelapse")
MAX_CAPTURES_PER_PAGE = 100


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


def _positive_query_int(name, default, maximum=None):
    raw = request.args.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} debe ser un entero") from error
    if value < 1:
        raise ValueError(f"{name} debe ser mayor que cero")
    return min(value, maximum) if maximum else value


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
            "light_enabled", "light_intensity", "folder_name",
            "light_warmup_seconds",
            "save_sensor_readings",
            "capture_overlay_enabled",
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
        light_warmup_seconds = data.get("light_warmup_seconds", 3)
        if isinstance(light_warmup_seconds, bool):
            raise ValueError("light_warmup_seconds debe ser un entero")
        try:
            light_warmup_seconds = int(light_warmup_seconds)
        except (TypeError, ValueError) as error:
            raise ValueError("light_warmup_seconds debe ser un entero") from error
        if not 0 <= light_warmup_seconds <= 60:
            raise ValueError("light_warmup_seconds debe estar entre 0 y 60")
        if light_enabled and interval < light_warmup_seconds:
            raise ValueError(
                "interval_seconds debe ser al menos igual a light_warmup_seconds cuando la luz está activa"
            )
        folder_name = data.get("folder_name", "default")
        save_sensor_readings = data.get("save_sensor_readings", True)
        if not isinstance(save_sensor_readings, bool):
            raise ValueError("save_sensor_readings debe ser booleano")
        capture_overlay_enabled = data.get("capture_overlay_enabled", False)
        if not isinstance(capture_overlay_enabled, bool):
            raise ValueError("capture_overlay_enabled debe ser booleano")
        status = get_timelapse_service().configure(
            interval_seconds=interval,
            width=width,
            height=height,
            auto_resume=auto_resume,
            light_enabled=light_enabled,
            light_intensity=light_intensity,
            light_warmup_seconds=light_warmup_seconds,
            folder_name=folder_name,
            save_sensor_readings=save_sensor_readings,
            capture_overlay_enabled=capture_overlay_enabled,
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


@timelapse_bp.route("/folders", methods=["GET"])
def timelapse_folders():
    service = get_timelapse_service()
    return jsonify({
        "folders": service.list_folders(),
        "selected": service.status()["folder_name"],
    })


@timelapse_bp.route("/captures", methods=["GET"])
def timelapse_captures():
    folder = request.args.get("folder", "")
    try:
        page = _positive_query_int("page", 1)
        per_page = _positive_query_int("per_page", 20, MAX_CAPTURES_PER_PAGE)
        captures = get_timelapse_service().list_captures(folder)
        total = len(captures)
        pages = math.ceil(total / per_page)
        start = (page - 1) * per_page
        return jsonify({
            "folder": folder,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "captures": captures[start:start + per_page],
        })
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404


def _zip_response(folder_name, capture_paths, archive_name):
    service = get_timelapse_service()
    archive = tempfile.NamedTemporaryFile(prefix="timelapse-", suffix=".zip", delete=False)
    archive.close()
    try:
        with zipfile.ZipFile(archive.name, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for capture in capture_paths:
                path = service.capture_path(folder_name, capture)
                output.write(path, arcname=path.relative_to(service.folder_path(folder_name)))
    except Exception:
        os.unlink(archive.name)
        raise

    @after_this_request
    def remove_archive(response):
        try:
            os.unlink(archive.name)
        except OSError:
            pass
        return response

    return send_file(
        archive.name,
        as_attachment=True,
        download_name=archive_name,
        mimetype="application/zip",
    )


@timelapse_bp.route("/folders/<folder_name>/download", methods=["GET"])
def download_timelapse_folder(folder_name):
    service = get_timelapse_service()
    try:
        captures = service.list_captures(folder_name)
        return _zip_response(
            folder_name,
            [capture["path"] for capture in captures],
            f"{folder_name}.zip",
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@timelapse_bp.route("/capture/download", methods=["GET"])
def download_timelapse_capture():
    try:
        path = get_timelapse_service().capture_path(
            request.args.get("folder", ""), request.args.get("path", "")
        )
        return send_file(path, as_attachment=True, download_name=path.name)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@timelapse_bp.route("/capture/preview", methods=["GET"])
def preview_timelapse_capture():
    try:
        path = get_timelapse_service().capture_path(
            request.args.get("folder", ""), request.args.get("path", "")
        )
        return send_file(path, as_attachment=False, conditional=True, max_age=3600)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@timelapse_bp.route("/captures/download", methods=["POST"])
def download_selected_captures():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Se requiere un objeto JSON"}), 400
    folder = data.get("folder")
    captures = data.get("captures")
    if not isinstance(captures, list) or not captures:
        return jsonify({"error": "Debe seleccionar al menos una captura"}), 400
    if len(captures) > 5000 or any(not isinstance(item, str) for item in captures):
        return jsonify({"error": "Selección de capturas inválida"}), 400
    captures = list(dict.fromkeys(captures))
    try:
        return _zip_response(folder, captures, f"{folder}-seleccion.zip")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@timelapse_bp.route("/captures", methods=["DELETE"])
def delete_timelapse_captures():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Se requiere un objeto JSON"}), 400
    folder = data.get("folder")
    captures = data.get("captures")
    if not isinstance(captures, list) or not captures:
        return jsonify({"error": "Debe seleccionar al menos una captura"}), 400
    if len(captures) > 5000 or any(not isinstance(item, str) for item in captures):
        return jsonify({"error": "Selección de capturas inválida"}), 400
    captures = list(dict.fromkeys(captures))
    try:
        deleted = get_timelapse_service().delete_captures(folder, captures)
        return jsonify({"ok": True, "deleted": deleted, "folder": folder})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 409


@timelapse_bp.route("/folders/<folder_name>", methods=["DELETE"])
def delete_timelapse_folder(folder_name):
    try:
        resumed = get_timelapse_service().delete_folder(folder_name)
        return jsonify({
            "ok": True,
            "deleted_folder": folder_name,
            "timelapse_resumed": resumed,
        })
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 409
