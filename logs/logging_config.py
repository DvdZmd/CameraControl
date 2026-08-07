import logging
import os
import queue
import re
import sys
import threading
import traceback
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler

from flask import g, has_request_context, request

from database.models import ApplicationLog, db


VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
SENSITIVE_ENV_NAMES = {
    "FLASK_SECRET_KEY", "TUYA_API_KEY", "TUYA_API_SECRET", "TUYA_PASSWORD",
    "TUYA_DEVICE_KEY",
}
AUTHORIZATION_PATTERN = re.compile(
    r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)([^\s,;]+)"
)


def normalize_level(value, default="INFO"):
    level = str(value or "").strip().upper()
    return level if level in VALID_LEVELS else default


def redact_text(value):
    text = str(value)
    for name in SENSITIVE_ENV_NAMES:
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return AUTHORIZATION_PATTERN.sub(r"\1[REDACTED]", text)


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.http_method = request.method
            record.request_path = request.path
        else:
            record.request_id = getattr(record, "request_id", "-")
            record.http_method = getattr(record, "http_method", None)
            record.request_path = getattr(record, "request_path", None)
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact_text(super().format(record))


class DatabaseLogHandler(logging.Handler):
    """Queue log records and persist them outside the originating request."""

    def __init__(self, app, *, max_queue_size, retention_days, max_rows):
        super().__init__()
        self.app = app
        self.retention_days = retention_days
        self.max_rows = max_rows
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="database-log-writer",
            daemon=True,
        )
        self._thread.start()

    def emit(self, record):
        try:
            exception_type = None
            traceback_text = None
            if record.exc_info:
                exception_type = record.exc_info[0].__name__
                traceback_text = "".join(traceback.format_exception(*record.exc_info))
            payload = {
                "timestamp": datetime.fromtimestamp(record.created, UTC).replace(tzinfo=None),
                "level": record.levelname,
                "logger_name": record.name,
                "message": redact_text(record.getMessage()),
                "module": record.module,
                "function": record.funcName,
                "line_number": record.lineno,
                "exception_type": exception_type,
                "traceback": redact_text(traceback_text) if traceback_text else None,
                "request_id": getattr(record, "request_id", None),
                "http_method": getattr(record, "http_method", None),
                "request_path": getattr(record, "request_path", None),
            }
            self._queue.put_nowait(payload)
        except queue.Full:
            self._fallback("Cola de logging SQLite llena; se descartó un evento")
        except Exception as error:
            self._fallback(f"No se pudo encolar un log SQLite: {error}")

    def _run(self):
        self._cleanup_database()
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                payload = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                with self.app.app_context():
                    db.session.add(ApplicationLog(**payload))
                    db.session.commit()
            except Exception as error:
                with self.app.app_context():
                    db.session.rollback()
                    db.session.remove()
                self._fallback(f"No se pudo persistir un log SQLite: {error}")
            finally:
                self._queue.task_done()

    def _cleanup_database(self):
        try:
            with self.app.app_context():
                cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=self.retention_days)
                ApplicationLog.query.filter(ApplicationLog.timestamp < cutoff).delete(
                    synchronize_session=False
                )
                total = ApplicationLog.query.count()
                excess = total - self.max_rows
                if excess > 0:
                    oldest_ids = [
                        item[0]
                        for item in db.session.query(ApplicationLog.id)
                        .order_by(ApplicationLog.timestamp.asc())
                        .limit(excess)
                        .all()
                    ]
                    if oldest_ids:
                        ApplicationLog.query.filter(ApplicationLog.id.in_(oldest_ids)).delete(
                            synchronize_session=False
                        )
                db.session.commit()
        except Exception as error:
            with self.app.app_context():
                db.session.rollback()
                db.session.remove()
            self._fallback(f"No se pudo aplicar retención de logs SQLite: {error}")

    def close(self):
        self._stop_event.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        super().close()

    @staticmethod
    def _fallback(message):
        sys.stderr.write(f"[CameraControl logging] {message}\n")


def _handler_level(value, default):
    return getattr(logging, normalize_level(value, default))


def configure_logging(app, config):
    """Connect Flask and module loggers to one standard logging pipeline."""
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(_handler_level(config.level, "INFO"))
    context_filter = RequestContextFilter()
    formatter = RedactingFormatter(
        "%(asctime)s [%(levelname)s] %(name)s [request_id=%(request_id)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if config.console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(_handler_level(config.console_level, "INFO"))
        console_handler.addFilter(context_filter)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if config.file_enabled:
        log_dir = os.path.dirname(config.file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            config.file_path,
            maxBytes=config.file_max_bytes,
            backupCount=config.file_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(_handler_level(config.file_level, "ERROR"))
        file_handler.addFilter(context_filter)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    app.logger.handlers.clear()
    app.logger.setLevel(logging.NOTSET)
    app.logger.propagate = True

    logging.getLogger("werkzeug").setLevel(_handler_level(config.werkzeug_level, "INFO"))
    logging.getLogger("sqlalchemy").setLevel(_handler_level(config.sqlalchemy_level, "WARNING"))
    logging.getLogger("bleak").setLevel(_handler_level(config.bleak_level, "WARNING"))
    logging.getLogger("tuya_iot").setLevel(_handler_level(config.tuya_level, "WARNING"))


def enable_database_logging(app, config):
    if not config.database_enabled:
        return None
    handler = DatabaseLogHandler(
        app,
        max_queue_size=config.database_queue_size,
        retention_days=config.database_retention_days,
        max_rows=config.database_max_rows,
    )
    handler.setLevel(_handler_level(config.database_level, "ERROR"))
    handler.addFilter(RequestContextFilter())
    logging.getLogger().addHandler(handler)
    return handler
