import os
import logging
import shutil
import subprocess
import threading
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/admin"
)
logger = logging.getLogger(__name__)
CPU_STAT_PATH = Path("/proc/stat")
THERMAL_PATHS = (
    Path("/sys/class/thermal/thermal_zone0/temp"),
    Path("/sys/devices/virtual/thermal/thermal_zone0/temp"),
)
THROTTLED_PATHS = (
    Path("/sys/devices/platform/soc/soc:firmware/get_throttled"),
    Path("/sys/firmware/raspberrypi/get_throttled"),
)
_cpu_sample_lock = threading.Lock()
_previous_cpu_sample = None


def _privileged_command(*args):
    """Build a non-interactive privileged command for local administration."""
    command = list(args)
    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if sudo is None:
            raise RuntimeError("Se requieren permisos de administrador y sudo no está instalado")
        command = [sudo, "-n", *command]
    return command


def _enable_bluetooth_adapter():
    """Unblock Bluetooth, start its service and power the default controller."""
    rfkill = shutil.which("rfkill")
    systemctl = shutil.which("systemctl")
    bluetoothctl = shutil.which("bluetoothctl")
    if not rfkill or not systemctl or not bluetoothctl:
        missing = [
            name for name, path in (
                ("rfkill", rfkill),
                ("systemctl", systemctl),
                ("bluetoothctl", bluetoothctl),
            ) if not path
        ]
        raise RuntimeError(f"Faltan herramientas del sistema: {', '.join(missing)}")

    commands = (
        _privileged_command(rfkill, "unblock", "bluetooth"),
        _privileged_command(systemctl, "enable", "--now", "bluetooth.service"),
        [bluetoothctl, "power", "on"],
    )
    for command in commands:
        try:
            subprocess.run(
                command, capture_output=True, check=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Timeout activando Bluetooth") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            if command[0].endswith("sudo") and exc.returncode == 1:
                detail = "sudo requiere autorización no interactiva para rfkill/systemctl"
            raise RuntimeError(detail or "El sistema rechazó la activación de Bluetooth") from exc

    return {"enabled": True, "powered": True}


def _read_cpu_sample():
    line = CPU_STAT_PATH.read_text(encoding="ascii").splitlines()[0]
    fields = line.split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("Formato inesperado en /proc/stat")
    values = [int(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def _cpu_usage_percent():
    global _previous_cpu_sample
    with _cpu_sample_lock:
        current = _read_cpu_sample()
        if _previous_cpu_sample is None:
            _previous_cpu_sample = current
            return None
        total_delta = current[0] - _previous_cpu_sample[0]
        idle_delta = current[1] - _previous_cpu_sample[1]
        _previous_cpu_sample = current
    if total_delta <= 0:
        return None
    return round(max(0.0, min(100.0, 100 * (total_delta - idle_delta) / total_delta)), 1)


def _cpu_temperature_c():
    for path in THERMAL_PATHS:
        try:
            millidegrees = int(path.read_text(encoding="ascii").strip())
            return round(millidegrees / 1000, 1)
        except (OSError, TypeError, ValueError):
            continue
    return None


def _parse_throttled_value(raw_value):
    value = raw_value.strip().lower()
    if "=" in value:
        value = value.rsplit("=", 1)[1]
    return int(value, 0)


def _throttled_flags():
    raw_flags = None
    for path in THROTTLED_PATHS:
        try:
            raw_flags = _parse_throttled_value(path.read_text(encoding="ascii"))
            break
        except (OSError, TypeError, ValueError):
            continue

    if raw_flags is None:
        vcgencmd = shutil.which("vcgencmd")
        if vcgencmd:
            try:
                result = subprocess.run(
                    [vcgencmd, "get_throttled"],
                    capture_output=True,
                    check=True,
                    text=True,
                    timeout=1,
                )
                raw_flags = _parse_throttled_value(result.stdout)
            except (OSError, subprocess.SubprocessError, TypeError, ValueError):
                pass

    if raw_flags is None:
        return None
    return {
        "raw": f"0x{raw_flags:x}",
        "undervoltage_now": bool(raw_flags & (1 << 0)),
        "undervoltage_occurred": bool(raw_flags & (1 << 16)),
    }


def _timelapse_storage_path():
    service = current_app.config.get("TIMELAPSE_SERVICE")
    defaults = getattr(service, "defaults", None)
    configured_path = getattr(defaults, "timelapse_dir", None)
    path = Path(configured_path) if configured_path else Path(__file__).resolve().parent.parent
    path = path.expanduser().resolve(strict=False)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _storage_status():
    usage = shutil.disk_usage(_timelapse_storage_path())
    free_percent = round(100 * usage.free / usage.total, 1) if usage.total > 0 else 0.0
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": free_percent,
    }


@admin_bp.route("/system-status", methods=["GET"])
def system_status():
    """Return lightweight Raspberry Pi health data without requiring root."""
    try:
        cpu_usage = _cpu_usage_percent()
    except (OSError, TypeError, ValueError):
        cpu_usage = None
    try:
        storage = _storage_status()
    except (OSError, TypeError, ValueError):
        storage = None
    return jsonify({
        "cpu_temperature_c": _cpu_temperature_c(),
        "cpu_usage_percent": cpu_usage,
        "power": _throttled_flags(),
        "storage": storage,
    })


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


@admin_bp.route("/bluetooth/enable", methods=["POST"])
def enable_bluetooth():
    """Enable and power the Raspberry Pi Bluetooth adapter on demand."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("confirm") is not True:
        return jsonify({
            "status": "error",
            "message": "Confirmación requerida para activar Bluetooth.",
        }), 400

    try:
        adapter = _enable_bluetooth_adapter()
    except RuntimeError as exc:
        logger.warning("No se pudo activar Bluetooth: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 503

    return jsonify({
        "status": "enabled",
        "message": "Bluetooth activado correctamente.",
        "adapter": adapter,
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
