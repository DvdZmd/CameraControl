import logging
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, g

from database.models import ApplicationLog, db
from config import LoggingConfig
from logs.logging_config import (
    DatabaseLogHandler,
    RequestContextFilter,
    configure_logging,
    redact_text,
)


def logging_config(file_path):
    return SimpleNamespace(
        level="INFO",
        console_enabled=False,
        console_level="INFO",
        file_enabled=True,
        file_level="ERROR",
        file_path=file_path,
        file_max_bytes=1024 * 1024,
        file_backup_count=2,
        werkzeug_level="WARNING",
        sqlalchemy_level="WARNING",
        bleak_level="WARNING",
        tuya_level="WARNING",
    )


class LoggingConfigurationTests(unittest.TestCase):
    def tearDown(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        root.setLevel(logging.WARNING)

    def test_file_handler_defaults_to_error_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "server.log")
            app = Flask(__name__)
            configure_logging(app, logging_config(log_path))

            logger = logging.getLogger("test.file")
            logger.info("mensaje informativo")
            logger.error("mensaje de error")
            for handler in logging.getLogger().handlers:
                handler.flush()

            contents = Path(log_path).read_text(encoding="utf-8")
            self.assertNotIn("mensaje informativo", contents)
            self.assertIn("mensaje de error", contents)

    def test_safe_default_destinations(self):
        keys = [
            "LOG_LEVEL", "LOG_CONSOLE_ENABLED", "LOG_FILE_ENABLED",
            "LOG_FILE_LEVEL", "LOG_DB_ENABLED", "LOG_DB_LEVEL",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            config = LoggingConfig()

        self.assertEqual(config.level, "INFO")
        self.assertTrue(config.file_enabled)
        self.assertEqual(config.file_level, "ERROR")
        self.assertFalse(config.database_enabled)
        self.assertEqual(config.database_level, "ERROR")

    def test_redacts_configured_secrets_and_authorization(self):
        with patch.dict(os.environ, {"TUYA_API_SECRET": "super-secret"}):
            value = redact_text(
                "secret=super-secret Authorization: Bearer abc.def.ghi"
            )
        self.assertNotIn("super-secret", value)
        self.assertNotIn("abc.def.ghi", value)
        self.assertIn("[REDACTED]", value)


class DatabaseLoggingTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self.tmpdir.name) / "logs.db"
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.tmpdir.cleanup()

    def test_database_handler_persists_metadata_and_request_context(self):
        handler = DatabaseLogHandler(
            self.app,
            max_queue_size=10,
            retention_days=30,
            max_rows=100,
        )
        handler.setLevel(logging.WARNING)
        handler.addFilter(RequestContextFilter())
        logger = logging.getLogger("test.database")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        with self.app.test_request_context("/api/test", method="POST"):
            g.request_id = "request-123"
            logger.info("no persistir")
            try:
                raise RuntimeError("fallo controlado")
            except RuntimeError:
                logger.exception("persistir error")

        handler.close()
        logger.handlers = []

        with self.app.app_context():
            records = ApplicationLog.query.all()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record.level, "ERROR")
            self.assertEqual(record.logger_name, "test.database")
            self.assertEqual(record.request_id, "request-123")
            self.assertEqual(record.http_method, "POST")
            self.assertEqual(record.request_path, "/api/test")
            self.assertEqual(record.exception_type, "RuntimeError")
            self.assertIn("fallo controlado", record.traceback)


if __name__ == "__main__":
    unittest.main()
