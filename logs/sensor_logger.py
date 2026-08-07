import math
import logging
import threading

from database.models import SensorLoggingSettings, SensorReading, db


TELEMETRY_FIELDS = {
    "temperature_air": "DT",
    "humidity_air": "DH",
    "temperature_soil": "DS",
    "humidity_soil": "SP",
}
logger = logging.getLogger(__name__)
SETTINGS_ID = 1


def _finite_float(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def reading_from_ble_state(state):
    """Build a complete environmental reading from a cached BLE payload."""
    if not isinstance(state, dict):
        return None

    values = {
        field: _finite_float(state.get(ble_key))
        for field, ble_key in TELEMETRY_FIELDS.items()
    }
    if any(value is None for value in values.values()):
        return None
    return SensorReading(**values)


def persist_current_telemetry(app, controller):
    """Persist one cached sample without performing BLE reads or scans."""
    client = getattr(controller, "client", None)
    if not client or not getattr(client, "is_connected", False):
        return False

    reading = reading_from_ble_state(getattr(controller, "last_state", None))
    if reading is None:
        return False

    with app.app_context():
        try:
            db.session.add(reading)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            logger.exception("No se pudo persistir la telemetría BLE")
            return False


class SensorLoggingRuntime:
    """Runtime reconfigurable backed by a singleton SQLite settings row."""

    def __init__(self, app, controller, defaults):
        self.app = app
        self.controller = controller
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.lock = threading.Lock()
        with app.app_context():
            settings = db.session.get(SensorLoggingSettings, SETTINGS_ID)
            if settings is None:
                settings = SensorLoggingSettings(
                    id=SETTINGS_ID,
                    enabled=defaults.enabled,
                    interval_seconds=defaults.interval_seconds,
                )
                db.session.add(settings)
                db.session.commit()
            self.enabled = bool(settings.enabled)
            self.interval_seconds = float(settings.interval_seconds)
        self.thread = threading.Thread(
            target=self._run,
            name="sensor-telemetry-logger",
            daemon=True,
        )

    def start(self):
        self.thread.start()

    def status(self):
        with self.lock:
            return {
                "enabled": self.enabled,
                "interval_seconds": self.interval_seconds,
            }

    def configure(self, *, enabled, interval_seconds):
        with self.app.app_context():
            settings = db.session.get(SensorLoggingSettings, SETTINGS_ID)
            if settings is None:
                settings = SensorLoggingSettings(id=SETTINGS_ID)
                db.session.add(settings)
            settings.enabled = enabled
            settings.interval_seconds = interval_seconds
            db.session.commit()
        with self.lock:
            self.enabled = enabled
            self.interval_seconds = interval_seconds
        self.wake_event.set()
        logger.info(
            "Persistencia de telemetría actualizada: enabled=%s intervalo=%.2fs",
            enabled,
            interval_seconds,
        )
        return self.status()

    def _run(self):
        while not self.stop_event.is_set():
            with self.lock:
                enabled = self.enabled
                interval_seconds = self.interval_seconds
            timeout = interval_seconds if enabled else None
            awakened = self.wake_event.wait(timeout)
            self.wake_event.clear()
            if self.stop_event.is_set():
                break
            if not awakened and enabled:
                persist_current_telemetry(self.app, self.controller)


def start_sensor_logger(app, controller, config):
    """Start the configurable daemon that snapshots cached ESP32 telemetry."""
    runtime = SensorLoggingRuntime(app, controller, config)
    runtime.start()
    logger.info(
        "Persistencia de telemetría BLE: enabled=%s intervalo=%.2fs",
        runtime.enabled,
        runtime.interval_seconds,
    )
    return runtime.thread, runtime.stop_event, runtime
