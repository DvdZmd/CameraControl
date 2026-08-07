import logging
import math
from datetime import UTC, datetime

from database.models import Esp32Settings, SensorReading, TimelapseConfig, db
from logs.sensor_logger import reading_from_ble_state


logger = logging.getLogger(__name__)
CONFIG_ID = 1
ESP32_SETTINGS_ID = 1


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


class TimelapseService:
    """Persist application policy while rpicam-z owns capture execution."""

    def __init__(self, app, camera_getter, ble_controller, defaults):
        self.app = app
        self.camera_getter = camera_getter
        self.ble_controller = ble_controller
        self.defaults = defaults

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
            config = TimelapseConfig(
                id=CONFIG_ID,
                interval_minutes=max(1, math.ceil(seconds / 60)),
                interval_seconds=seconds,
                width=3840,
                height=2160,
                is_running=False,
                auto_resume=self.defaults.auto_resume,
                save_path=self.defaults.timelapse_dir,
            )
            db.session.add(config)
            db.session.commit()
        elif not config.save_path:
            config.save_path = self.defaults.timelapse_dir
            db.session.commit()
        return config

    def configure(
        self, *, interval_seconds, width, height, auto_resume,
        light_enabled=False, light_intensity=100,
    ):
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
        camera = self.camera_getter()
        runtime = self._runtime_status(camera)
        if runtime.get("running"):
            config.is_running = True
            db.session.commit()
            return self.status()

        camera.save_path = config.save_path or self.defaults.timelapse_dir
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
            started = camera.start_timelapse(
                config.interval_seconds,
                config.width,
                config.height,
                on_capture=self._on_capture,
                on_error=self._on_error,
                on_complete=self._on_complete,
                on_before_capture=self._on_before_capture,
            )
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
            "save_path": config.save_path,
            "capture_count": config.capture_count,
            "started_at": config.started_at.isoformat() if config.started_at else None,
            "stopped_at": config.stopped_at.isoformat() if config.stopped_at else None,
            "last_capture_at": config.last_capture_at.isoformat() if config.last_capture_at else None,
            "last_capture_path": config.last_capture_path,
            "last_error": config.last_error or runtime.get("last_error"),
            "runtime": runtime,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    def _runtime_status(self, camera=None):
        camera = camera or self.camera_getter()
        try:
            status_getter = getattr(camera, "get_timelapse_status", None)
            if callable(status_getter):
                return status_getter()
            return {"running": bool(getattr(camera, "timelapse_active", False))}
        except Exception as error:
            return {"running": False, "last_error": str(error)}

    def _on_capture(self, metadata):
        with self.app.app_context():
            self._restore_manual_light()
            config = self.ensure_default_config()
            config.capture_count = (config.capture_count or 0) + 1
            config.last_capture_at = _parse_datetime(metadata.get("captured_at")) or _utc_now()
            config.last_capture_path = metadata.get("path")
            config.last_error = None
            config.updated_at = _utc_now()

            state = getattr(self.ble_controller, "last_state", None)
            reading = reading_from_ble_state(state)
            if reading is not None:
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
            intensity = config.light_intensity if config.light_enabled else 0
            try:
                self._set_light(intensity)
                logger.debug("Luz de timelapse aplicada antes de captura: %s%%", intensity)
            except Exception as error:
                # El ESP32 es hardware opcional: su ausencia no debe cancelar
                # una captura que la cámara todavía puede realizar.
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
