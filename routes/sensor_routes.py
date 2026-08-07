from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, current_app, jsonify, request

from database.models import SensorReading


sensor_bp = Blueprint("sensors", __name__, url_prefix="/api/sensors")
MAX_PER_PAGE = 100


def _positive_int(name, default, maximum=None):
    raw = request.args.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} debe ser un entero") from error
    if value < 1:
        raise ValueError(f"{name} debe ser mayor que cero")
    return min(value, maximum) if maximum else value


def _optional_float(name):
    raw = request.args.get(name)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} debe ser numérico") from error


def _optional_date(name):
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError(f"{name} debe usar el formato YYYY-MM-DD") from error


def _serialize(reading):
    return {
        "id": reading.id,
        "timestamp": _utc_isoformat(reading.timestamp),
        "temperature_air": reading.temperature_air,
        "humidity_air": reading.humidity_air,
        "temperature_soil": reading.temperature_soil,
        "humidity_soil": reading.humidity_soil,
        "pan_pulse_us": reading.pan_pulse_us,
        "tilt_pulse_us": reading.tilt_pulse_us,
    }


def _utc_isoformat(value):
    """Serialize SQLite's naive UTC datetimes with an explicit UTC marker."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _local_midnight_as_utc(value):
    timezone_name = current_app.config.get(
        "APP_TIMEZONE", "America/Argentina/Buenos_Aires"
    )
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Zona horaria no válida: {timezone_name}") from error
    local_midnight = datetime.combine(value, time.min, tzinfo=local_timezone)
    return local_midnight.astimezone(UTC).replace(tzinfo=None)


@sensor_bp.route("/readings", methods=["GET"])
def readings_history():
    try:
        page = _positive_int("page", 1)
        per_page = _positive_int("per_page", 20, MAX_PER_PAGE)
        start_date = _optional_date("start_date")
        end_date = _optional_date("end_date")

        ranges = {
            "temperature_air": (
                _optional_float("min_temperature_air"),
                _optional_float("max_temperature_air"),
            ),
            "humidity_air": (
                _optional_float("min_humidity_air"),
                _optional_float("max_humidity_air"),
            ),
            "temperature_soil": (
                _optional_float("min_temperature_soil"),
                _optional_float("max_temperature_soil"),
            ),
            "humidity_soil": (
                _optional_float("min_humidity_soil"),
                _optional_float("max_humidity_soil"),
            ),
        }
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date no puede ser posterior a end_date")
        for field, (minimum, maximum) in ranges.items():
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"El mínimo de {field} no puede superar el máximo")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    query = SensorReading.query
    if start_date:
        query = query.filter(SensorReading.timestamp >= _local_midnight_as_utc(start_date))
    if end_date:
        query = query.filter(
            SensorReading.timestamp < _local_midnight_as_utc(end_date + timedelta(days=1))
        )
    for field, (minimum, maximum) in ranges.items():
        column = getattr(SensorReading, field)
        if minimum is not None:
            query = query.filter(column >= minimum)
        if maximum is not None:
            query = query.filter(column <= maximum)

    pagination = query.order_by(SensorReading.timestamp.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify({
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "readings": [_serialize(reading) for reading in pagination.items],
    })
