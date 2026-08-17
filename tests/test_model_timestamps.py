import unittest
import warnings
from datetime import UTC, datetime, timedelta

from flask import Flask

from database.models import CameraSettings, SensorReading, db, utc_now_naive


class ModelTimestampTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    def test_utc_now_naive_preserves_sqlite_storage_convention(self):
        before = datetime.now(UTC).replace(tzinfo=None)
        value = utc_now_naive()
        after = datetime.now(UTC).replace(tzinfo=None)

        self.assertIsNone(value.tzinfo)
        self.assertLessEqual(before, value)
        self.assertLessEqual(value, after)

    def test_model_defaults_do_not_call_deprecated_datetime_utcnow(self):
        reading = SensorReading(
            temperature_air=20.0,
            humidity_air=80.0,
            temperature_soil=19.0,
            humidity_soil=70.0,
        )

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "error",
                message=r"datetime\.datetime\.utcnow\(\) is deprecated.*",
                category=DeprecationWarning,
            )
            db.session.add(reading)
            db.session.commit()

        self.assertIsNotNone(reading.timestamp)
        self.assertIsNone(reading.timestamp.tzinfo)
        self.assertLess(
            abs(datetime.now(UTC).replace(tzinfo=None) - reading.timestamp),
            timedelta(seconds=5),
        )

    def test_onupdate_keeps_utc_naive_datetime(self):
        settings = CameraSettings(
            camera_key="test-camera",
            width=1280,
            height=720,
        )
        db.session.add(settings)
        db.session.commit()

        settings.width = 1920
        db.session.commit()

        self.assertIsNotNone(settings.updated_at)
        self.assertIsNone(settings.updated_at.tzinfo)


if __name__ == "__main__":
    unittest.main()
