import logging
import math
import re
import shutil
import inspect
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database.models import (
    Esp32Settings,
    SensorLoggingSettings,
    SensorReading,
    TimelapseConfig,
    db,
)
from logs.sensor_logger import reading_from_ble_state


logger = logging.getLogger(__name__)
CONFIG_ID = 1
ESP32_SETTINGS_ID = 1
SENSOR_LOGGING_SETTINGS_ID = 1
DEFAULT_FOLDER_NAME = "default"
FOLDER_NAME_PATTERN = re.compile(r"^[\w .-]{1,100}$", re.UNICODE)
CAPTURE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
FOLDER_MARKER = ".cameracontrol-timelapse"
DEFAULT_LIGHT_WARMUP_SECONDS = 3
MAX_LIGHT_WARMUP_SECONDS = 60


def _utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utc_isoformat(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _capture_filename(captured_at):
    return f"{captured_at.strftime('%Y_%m_%d_%H-%M-%S')}.jpg"


def _unique_capture_path(directory, filename, *, current_path=None):
    candidate = directory / filename
    counter = 2
    while candidate.exists() and candidate != current_path:
        candidate = directory / f"{Path(filename).stem}_{counter}.jpg"
        counter += 1
    return candidate


class TimelapseService:
    """Persist application policy while rpicam-z owns capture execution."""

    def __init__(self, app, camera_getter, ble_controller, defaults):
        self.app = app
        self.camera_getter = camera_getter
        self.ble_controller = ble_controller
        self.defaults = defaults
        self._compat_stop_event = threading.Event()
        self._compat_thread = None
        self._compat_last_error = None

    def ensure_schema(self):
        with db.engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(timelapse_config)")
            }
            migrations = {
                "interval_seconds": "ALTER TABLE timelapse_config ADD COLUMN interval_seconds INTEGER NOT NULL DEFAULT 10",
                "auto_resume": "ALTER TABLE timelapse_config ADD COLUMN auto_resume BOOLEAN NOT NULL DEFAULT 1",
                "save_path": "ALTER TABLE timelapse_config ADD COLUMN save_path VARCHAR(2048)",
                "started_at": "ALTER TABLE timelapse_config ADD COLUMN started_at DATETIME",
                "stopped_at": "ALTER TABLE timelapse_config ADD COLUMN stopped_at DATETIME",
                "last_capture_at": "ALTER TABLE timelapse_config ADD COLUMN last_capture_at DATETIME",
                "last_capture_path": "ALTER TABLE timelapse_config ADD COLUMN last_capture_path VARCHAR(4096)",
                "capture_count": "ALTER TABLE timelapse_config ADD COLUMN capture_count INTEGER NOT NULL DEFAULT 0",
                "last_error": "ALTER TABLE timelapse_config ADD COLUMN last_error TEXT",
                "light_enabled": "ALTER TABLE timelapse_config ADD COLUMN light_enabled BOOLEAN NOT NULL DEFAULT 0",
                "light_intensity": "ALTER TABLE timelapse_config ADD COLUMN light_intensity INTEGER NOT NULL DEFAULT 100",
                "light_warmup_seconds": "ALTER TABLE timelapse_config ADD COLUMN light_warmup_seconds INTEGER NOT NULL DEFAULT 3",
                "folder_name": "ALTER TABLE timelapse_config ADD COLUMN folder_name VARCHAR(120) NOT NULL DEFAULT 'default'",
            }
            added_interval_seconds = "interval_seconds" not in columns
            for column, statement in migrations.items():
                if column not in columns:
                    connection.exec_driver_sql(statement)
            if added_interval_seconds and "interval_minutes" in columns:
                connection.exec_driver_sql(
                    "UPDATE timelapse_config SET interval_seconds = "
                    "CASE WHEN interval_minutes > 0 THEN interval_minutes * 60 ELSE 10 END"
                )

    def ensure_default_config(self):
        config = db.session.get(TimelapseConfig, CONFIG_ID)
        if config is None:
            seconds = self.defaults.default_interval_seconds
            default_path = self.folder_path(DEFAULT_FOLDER_NAME, create=True)
            config = TimelapseConfig(
                id=CONFIG_ID,
                interval_minutes=max(1, math.ceil(seconds / 60)),
                interval_seconds=seconds,
                width=3840,
                height=2160,
                is_running=False,
                auto_resume=self.defaults.auto_resume,
                save_path=str(default_path),
                folder_name=DEFAULT_FOLDER_NAME,
            )
            db.session.add(config)
            db.session.commit()
        elif not config.save_path:
            config.save_path = self.defaults.timelapse_dir
            db.session.commit()
        return config

    @property
    def root_path(self):
        root = Path(self.defaults.timelapse_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def validate_folder_name(self, folder_name):
        if not isinstance(folder_name, str):
            raise ValueError("folder_name debe ser texto")
        normalized = folder_name.strip()
        if (
            not normalized
            or normalized in {".", ".."}
            or normalized.startswith(".")
            or not FOLDER_NAME_PATTERN.fullmatch(normalized)
        ):
            raise ValueError(
                "folder_name admite letras, números, espacios, guion, punto y guion bajo"
            )
        return normalized

    def folder_path(self, folder_name, *, create=False):
        normalized = self.validate_folder_name(folder_name)
        path = (self.root_path / normalized).resolve()
        if path.parent != self.root_path:
            raise ValueError("La carpeta debe estar dentro del directorio de timelapse")
        if create:
            path.mkdir(parents=False, exist_ok=True)
            (path / FOLDER_MARKER).touch(exist_ok=True)
        if not path.is_dir():
            raise FileNotFoundError(f"No existe la carpeta de timelapse: {normalized}")
        return path

    def list_folders(self):
        folders = []
        for path in self.root_path.iterdir():
            if not path.is_dir() or path.is_symlink() or path.name.startswith("."):
                continue
            marked = (path / FOLDER_MARKER).is_file()
            has_captures = any(
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.suffix.lower() in CAPTURE_EXTENSIONS
                for candidate in path.rglob("*")
            )
            if marked or has_captures:
                folders.append(path.name)
        return sorted(folders, key=str.casefold)

    def list_captures(self, folder_name):
        folder = self.folder_path(folder_name)
        captures = []
        for path in folder.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if path.suffix.lower() not in CAPTURE_EXTENSIONS:
                continue
            resolved = path.resolve()
            if folder not in resolved.parents:
                continue
            stat = resolved.stat()
            captures.append({
                "path": resolved.relative_to(folder).as_posix(),
                "name": resolved.name,
                "size_bytes": stat.st_size,
                "modified_at": _utc_isoformat(
                    datetime.fromtimestamp(stat.st_mtime, UTC)
                ),
            })
        captures.sort(key=lambda item: item["modified_at"], reverse=True)
        return captures

    def capture_path(self, folder_name, relative_path):
        folder = self.folder_path(folder_name)
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("La ruta de captura es requerida")
        path = (folder / relative_path).resolve()
        if folder not in path.parents or path.suffix.lower() not in CAPTURE_EXTENSIONS:
            raise ValueError("Ruta de captura inválida")
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError("La captura no existe")
        return path

    def delete_captures(self, folder_name, relative_paths):
        folder = self.folder_path(folder_name)
        self._assert_folder_not_active(folder_name)
        paths = [self.capture_path(folder_name, value) for value in relative_paths]
        for path in paths:
            path.unlink()
        # rpicam-z crea subdirectorios por fecha/sesión. Se podan solamente los
        # que quedaron vacíos, sin eliminar la carpeta seleccionable ni marker.
        for directory in sorted(
            (path for path in folder.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        return len(paths)

    def delete_folder(self, folder_name):
        folder = self.folder_path(folder_name)
        self._assert_folder_not_active(folder_name)
        shutil.rmtree(folder)
        logger.info("Carpeta de timelapse eliminada: %s", folder)

    def _assert_folder_not_active(self, folder_name):
        config = self.ensure_default_config()
        if (
            self._runtime_status().get("running")
            and config.folder_name == self.validate_folder_name(folder_name)
        ):
            raise RuntimeError("No se pueden borrar archivos del timelapse activo")

    def configure(
        self, *, interval_seconds, width, height, auto_resume,
        light_enabled=False, light_intensity=100,
        light_warmup_seconds=DEFAULT_LIGHT_WARMUP_SECONDS,
        folder_name=DEFAULT_FOLDER_NAME,
    ):
        if not 0 <= light_warmup_seconds <= MAX_LIGHT_WARMUP_SECONDS:
            raise ValueError(
                f"light_warmup_seconds debe estar entre 0 y {MAX_LIGHT_WARMUP_SECONDS}"
            )
        if light_enabled and interval_seconds < light_warmup_seconds:
            raise ValueError(
                f"El intervalo debe ser de al menos {light_warmup_seconds} segundos cuando la luz está activa"
            )
        config = self.ensure_default_config()
        if self._runtime_status().get("running"):
            raise RuntimeError("No se puede cambiar la configuración con el timelapse activo")
        config.interval_seconds = interval_seconds
        config.interval_minutes = max(1, math.ceil(interval_seconds / 60))
        config.width = width
        config.height = height
        config.auto_resume = auto_resume
        config.light_enabled = light_enabled
        config.light_intensity = light_intensity
        config.light_warmup_seconds = light_warmup_seconds
        config.folder_name = self.validate_folder_name(folder_name)
        config.save_path = str(self.folder_path(config.folder_name, create=True))
        config.updated_at = _utc_now()
        db.session.commit()
        logger.info(
            "Configuración de timelapse guardada: intervalo=%ss resolución=%sx%s auto_resume=%s luz=%s intensidad=%s%%",
            interval_seconds,
            width,
            height,
            auto_resume,
            light_enabled,
            light_intensity,
        )
        return self.status()

    def start(self, *, resuming=False):
        config = self.ensure_default_config()
        if config.light_enabled and config.interval_seconds < config.light_warmup_seconds:
            raise ValueError(
                f"El intervalo persistido debe ser de al menos {config.light_warmup_seconds} segundos cuando la luz está activa"
            )
        camera = self.camera_getter()
        runtime = self._runtime_status(camera)
        if runtime.get("running"):
            config.is_running = True
            db.session.commit()
            return self.status()

        selected_path = self.folder_path(config.folder_name, create=True)
        camera.save_path = str(selected_path)
        config.save_path = str(selected_path)
        camera.timelapse_organize_by_date = True
        config.is_running = True
        config.last_error = None
        config.stopped_at = None
        if not resuming:
            config.capture_count = 0
            config.last_capture_at = None
            config.last_capture_path = None
            config.started_at = _utc_now()
        elif config.started_at is None:
            config.started_at = _utc_now()
        config.updated_at = _utc_now()
        db.session.commit()

        try:
            if self._supports_native_callbacks(camera):
                started = camera.start_timelapse(
                    config.interval_seconds,
                    config.width,
                    config.height,
                    on_capture=self._on_capture,
                    on_error=self._on_error,
                    on_complete=self._on_complete,
                    on_before_capture=self._on_before_capture,
                )
            else:
                started = self._start_compat_timelapse(camera, config)
        except Exception as error:
            config.last_error = str(error)
            if not resuming:
                config.is_running = False
            db.session.commit()
            logger.exception("No se pudo iniciar el timelapse")
            raise

        if started is False and not self._runtime_status(camera).get("running"):
            config.is_running = False
            config.last_error = "rpicam-z rechazó el inicio del timelapse"
            db.session.commit()
            raise RuntimeError("rpicam-z rechazó el inicio del timelapse")

        logger.info(
            "%s timelapse cada %s segundos a %sx%s",
            "Reanudado" if resuming else "Iniciado",
            config.interval_seconds,
            config.width,
            config.height,
        )
        return self.status()

    def stop(self):
        config = self.ensure_default_config()
        camera = self.camera_getter()
        stop_error = None
        try:
            if self._compat_thread and self._compat_thread.is_alive():
                stopped = self._stop_compat_timelapse()
            else:
                stopped = camera.stop_timelapse()
        except Exception as error:
            stopped = False
            stop_error = str(error)
            logger.warning("No se pudo detener el runtime de timelapse: %s", error)
        config.is_running = False
        config.stopped_at = _utc_now()
        config.updated_at = _utc_now()
        if stopped is False:
            config.last_error = stop_error or "El thread de timelapse no finalizó dentro del timeout"
            logger.error(config.last_error)
        else:
            config.last_error = None
            logger.info("Timelapse detenido")
        db.session.commit()
        return self.status()

    def resume_if_needed(self):
        config = self.ensure_default_config()
        if not config.is_running or not config.auto_resume:
            return False
        try:
            self.start(resuming=True)
            return True
        except Exception as error:
            config.last_error = f"No se pudo reanudar automáticamente: {error}"
            db.session.commit()
            logger.warning("Timelapse pendiente de reanudación: %s", error)
            return False

    def status(self):
        config = self.ensure_default_config()
        runtime = self._runtime_status()
        return {
            "running": bool(runtime.get("running")),
            "desired_running": bool(config.is_running),
            "auto_resume": bool(config.auto_resume),
            "interval_seconds": config.interval_seconds,
            "width": config.width,
            "height": config.height,
            "light_enabled": bool(config.light_enabled),
            "light_intensity": config.light_intensity,
            "light_warmup_seconds": config.light_warmup_seconds,
            "folder_name": config.folder_name or DEFAULT_FOLDER_NAME,
            "root_path": str(self.root_path),
            "save_path": config.save_path,
            "capture_count": config.capture_count,
            "started_at": _utc_isoformat(config.started_at),
            "stopped_at": _utc_isoformat(config.stopped_at),
            "last_capture_at": _utc_isoformat(config.last_capture_at),
            "last_capture_path": config.last_capture_path,
            "last_error": config.last_error or runtime.get("last_error"),
            "runtime": runtime,
            "updated_at": _utc_isoformat(config.updated_at),
        }

    def _runtime_status(self, camera=None):
        compat_thread = self._compat_thread
        if compat_thread is not None and compat_thread.is_alive():
            return {
                "running": True,
                "mode": "compatibility",
                "last_error": self._compat_last_error,
            }
        camera = camera or self.camera_getter()
        try:
            status_getter = getattr(camera, "get_timelapse_status", None)
            if callable(status_getter):
                return status_getter()
            return {"running": bool(getattr(camera, "timelapse_active", False))}
        except Exception as error:
            return {"running": False, "last_error": str(error)}

    @staticmethod
    def _supports_native_callbacks(camera):
        try:
            parameters = inspect.signature(camera.start_timelapse).parameters
        except (TypeError, ValueError):
            return False
        if any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            return True
        required_callbacks = {
            "on_before_capture",
            "on_capture",
            "on_error",
            "on_complete",
        }
        return required_callbacks.issubset(parameters)

    def _start_compat_timelapse(self, camera, config):
        if self._compat_thread and self._compat_thread.is_alive():
            return False
        self._compat_stop_event.clear()
        self._compat_last_error = None
        self._compat_thread = threading.Thread(
            target=self._compat_timelapse_worker,
            args=(
                camera,
                config.interval_seconds,
                config.width,
                config.height,
                Path(config.save_path),
            ),
            name="timelapse-compatibility-worker",
            daemon=True,
        )
        self._compat_thread.start()
        logger.warning(
            "rpicam-z no soporta el ciclo completo de callbacks (incluido "
            "on_before_capture); se usa el worker compatible de CameraControl"
        )
        return True

    def _stop_compat_timelapse(self):
        self._compat_stop_event.set()
        thread = self._compat_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5)
        stopped = not (thread and thread.is_alive())
        if stopped:
            self._compat_thread = None
        return stopped

    def _capture_local_now(self):
        timezone_name = self.app.config.get(
            "APP_TIMEZONE", "America/Argentina/Buenos_Aires"
        )
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            return datetime.now(UTC)

    def _compat_timelapse_worker(self, camera, interval, width, height, save_path):
        started_at = self._capture_local_now()
        session_path = save_path / started_at.strftime("%Y-%m-%d") / started_at.strftime("%H-%M-%S")
        session_path.mkdir(parents=True, exist_ok=True)
        capture_count = 0
        reason = "stopped"
        try:
            while not self._compat_stop_event.is_set():
                cycle_started = time.monotonic()
                metadata = {"capture_count": capture_count + 1}
                try:
                    self._on_before_capture(metadata)
                    if self._compat_stop_event.is_set():
                        break
                    frame = camera.take_custom_photo(width, height)
                    if not frame:
                        raise RuntimeError("La cámara no devolvió bytes JPEG")
                    captured_at = self._capture_local_now()
                    capture_path = _unique_capture_path(
                        session_path,
                        _capture_filename(captured_at),
                    )
                    capture_path.write_bytes(frame)
                    capture_count += 1
                    self._compat_last_error = None
                    self._on_capture({
                        "captured_at": captured_at.astimezone(UTC).isoformat(),
                        "path": str(capture_path),
                        "capture_count": capture_count,
                        "width": width,
                        "height": height,
                    })
                except Exception as error:
                    self._compat_last_error = str(error)
                    self._on_error({"error": str(error), "capture_count": capture_count})
                    logger.exception("Error en captura del worker compatible de timelapse")
                elapsed = time.monotonic() - cycle_started
                if self._compat_stop_event.wait(max(0, interval - elapsed)):
                    break
        except Exception as error:
            reason = "error"
            self._compat_last_error = str(error)
            logger.exception("El worker compatible de timelapse finalizó inesperadamente")
        finally:
            self._on_complete({"reason": reason, "capture_count": capture_count})

    def _on_capture(self, metadata):
        with self.app.app_context():
            self._restore_manual_light()
            config = self.ensure_default_config()
            captured_at = _parse_datetime(metadata.get("captured_at")) or _utc_now()
            capture_path = metadata.get("path")
            if capture_path:
                source = Path(capture_path).resolve()
                folder = self.folder_path(config.folder_name)
                if source.is_file() and folder in source.parents:
                    destination = _unique_capture_path(
                        source.parent,
                        _capture_filename(captured_at),
                        current_path=source,
                    )
                    if destination != source:
                        source.rename(destination)
                    capture_path = str(destination)
                    metadata["path"] = capture_path
            config.capture_count = (config.capture_count or 0) + 1
            config.last_capture_at = captured_at
            config.last_capture_path = capture_path
            config.last_error = None
            config.updated_at = _utc_now()

            state = getattr(self.ble_controller, "last_state", None)
            reading = reading_from_ble_state(state)
            logging_settings = db.session.get(
                SensorLoggingSettings, SENSOR_LOGGING_SETTINGS_ID
            )
            logging_enabled = logging_settings is None or logging_settings.enabled
            if logging_enabled and reading is not None:
                reading.timestamp = config.last_capture_at
                reading.pan_pulse_us = _optional_int(state.get("P"))
                reading.tilt_pulse_us = _optional_int(state.get("T"))
                db.session.add(reading)
            db.session.commit()
            logger.info("Captura de timelapse guardada: %s", config.last_capture_path)

    def _on_error(self, metadata):
        with self.app.app_context():
            self._restore_manual_light()
            config = self.ensure_default_config()
            config.last_error = metadata.get("error", "Error de captura no especificado")
            config.updated_at = _utc_now()
            db.session.commit()
            logger.error("Error de captura de timelapse: %s", config.last_error)

    def _on_complete(self, metadata):
        with self.app.app_context():
            self._restore_manual_light()
        logger.info("Thread de timelapse finalizado: %s", metadata.get("reason", "unknown"))

    def _set_light(self, intensity):
        self.ble_controller.send_command_sync(f"SET_LIGHT:{intensity}")
        state = getattr(self.ble_controller, "last_state", None)
        if isinstance(state, dict):
            state["L"] = str(intensity)

    def _on_before_capture(self, metadata):
        """Apply this timelapse's light policy in the capture worker."""
        with self.app.app_context():
            config = self.ensure_default_config()
            light_enabled = bool(config.light_enabled)
            intensity = config.light_intensity if light_enabled else 0
            warmup_seconds = config.light_warmup_seconds or 0
        try:
            self._set_light(intensity)
            if light_enabled:
                if threading.current_thread() is self._compat_thread:
                    self._compat_stop_event.wait(warmup_seconds)
                else:
                    time.sleep(warmup_seconds)
            logger.debug(
                "Luz de timelapse aplicada antes de captura: %s%%; estabilización=%ss",
                intensity,
                warmup_seconds if light_enabled else 0,
            )
        except Exception as error:
            # El ESP32 es hardware opcional: su ausencia no debe cancelar una
            # captura que la cámara todavía puede realizar.
            logger.warning(
                "No se pudo aplicar la luz de timelapse antes de la captura: %s",
                error,
            )

    def _restore_manual_light(self):
        settings = db.session.get(Esp32Settings, ESP32_SETTINGS_ID)
        intensity = 0
        if settings is not None and settings.light_on:
            intensity = settings.light_intensity if settings.light_intensity is not None else 100
        try:
            self._set_light(intensity)
        except Exception as error:
            logger.warning("No se pudo restaurar la luz manual después de la captura: %s", error)
