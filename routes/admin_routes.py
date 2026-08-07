import os
import logging
import shutil
import subprocess
import threading
import time

from flask import Blueprint, jsonify, request


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/admin"
)
logger = logging.getLogger(__name__)


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
    except OSError:
        logger.exception("Error al disparar update.sh")


def _reboot_command():
    systemctl = shutil.which("systemctl")
    reboot = shutil.which("reboot")

    command = [systemctl, "reboot"] if systemctl else [reboot]
    if command[0] is None:
        raise RuntimeError("No se encontró systemctl ni reboot en el sistema")

    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if sudo:
            command.insert(0, sudo)

    return command


def _run_reboot_command(command):
    time.sleep(0.5)
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        logger.exception("Error al disparar reboot")


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
        "message": "Script de actualización disparado correctamente.",
    })


@admin_bp.route("/reboot", methods=["POST"])
def trigger_reboot():
    """
    Trigger a Raspberry Pi reboot after returning the HTTP response.

    The endpoint requires an explicit JSON confirmation to reduce accidental
    invocation from a stray POST.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("confirm") is not True:
        return jsonify({
            "status": "error",
            "message": "Confirmación requerida para reiniciar la Raspberry Pi.",
        }), 400

    try:
        command = _reboot_command()
    except RuntimeError as ex:
        return jsonify({
            "status": "error",
            "message": str(ex),
        }), 500

    reboot_thread = threading.Thread(
        target=_run_reboot_command,
        args=(command,),
        daemon=True,
    )

    try:
        reboot_thread.start()
    except RuntimeError as ex:
        return jsonify({
            "status": "error",
            "message": f"No se pudo disparar el reinicio: {ex}",
        }), 500

    return jsonify({
        "status": "rebooting",
        "message": "Reinicio de Raspberry Pi disparado correctamente.",
    }), 202
