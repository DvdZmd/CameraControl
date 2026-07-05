import os
import subprocess
import threading
import time

from flask import Blueprint, jsonify


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/admin"
)


def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run_update_script(script_path, project_root):
    time.sleep(0.5)
    try:
        log_dir = os.path.join(project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "update.log")

        with open(log_path, "ab") as update_log:
            subprocess.Popen(
                ["/bin/bash", script_path],
                cwd=project_root,
                stdout=update_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as ex:
        print(f"Error al disparar update.sh: {ex}")


@admin_bp.route("/update", methods=["POST"])
def trigger_update():
    """
    Trigger the on-demand software update script.

    The script is started shortly after returning the HTTP response because it
    may restart the Flask service as its final step.
    """
    project_root = _project_root()
    script_path = os.path.join(project_root, "update.sh")

    if not os.path.isfile(script_path):
        return jsonify({
            "status": "error",
            "message": "No se encontró el script update.sh.",
        }), 500

    update_thread = threading.Thread(
        target=_run_update_script,
        args=(script_path, project_root),
        daemon=True,
    )

    try:
        update_thread.start()
    except RuntimeError as ex:
        return jsonify({
            "status": "error",
            "message": f"No se pudo disparar la actualización: {ex}",
        }), 500

    return jsonify({
        "status": "updating",
        "message": "Script de actualización disparado correctamente...",
    })
