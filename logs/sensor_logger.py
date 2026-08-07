import math
import logging
import threading

from database.models import SensorReading, db


TELEMETRY_FIELDS = {
    "temperature_air": "DT",
    "humidity_air": "DH",
    "temperature_soil": "DS",
    "humidity_soil": "SP",
}
logger = logging.getLogger(__name__)


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


def _sensor_logging_loop(app, controller, interval_seconds, stop_event):
    while not stop_event.wait(interval_seconds):
        persist_current_telemetry(app, controller)


def start_sensor_logger(app, controller, config):
    """Start the daemon that periodically snapshots cached ESP32 telemetry."""
    if not config.enabled:
        logger.info("Persistencia de telemetría BLE deshabilitada")
        return None, None

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_sensor_logging_loop,
        args=(app, controller, config.interval_seconds, stop_event),
        name="sensor-telemetry-logger",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Persistencia de telemetría BLE iniciada cada %.2f segundos",
        config.interval_seconds,
    )
    return thread, stop_event
