import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from database.models import SensorReading, TimelapseConfig, db
from routes.timelapse_routes import timelapse_bp
from timelapse.service import TimelapseService


class FakeTimelapseCamera:
    def __init__(self):
        self.running = False
        self.save_path = None
        self.timelapse_organize_by_date = False
        self.start_calls = []
        self.callbacks = {}

    def start_timelapse(self, interval, width, height, **callbacks):
        if self.running:
            return False
        self.running = True
        self.start_calls.append((interval, width, height))
        self.callbacks = callbacks
        return True

    def stop_timelapse(self):
        self.running = False
        callback = self.callbacks.get("on_complete")
        if callback:
            callback({"reason": "stopped"})
        return True

    def get_timelapse_status(self):
        return {"running": self.running, "last_error": None}


class UnavailableTimelapseCamera:
    def get_timelapse_status(self):
        raise RuntimeError("cámara no disponible")

    def stop_timelapse(self):
        raise RuntimeError("cámara no disponible")


class TimelapseRoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.camera = FakeTimelapseCamera()
        self.ble = SimpleNamespace(last_state={
            "DT": "22.5", "DH": "81", "DS": "19.2", "SP": "64",
            "P": "1450", "T": "1520",
        }, commands=[])
        self.ble.send_command_sync = lambda command: self.ble.commands.append(command) or {"ok": True}
        defaults = SimpleNamespace(
            default_interval_seconds=10,
            auto_resume=True,
            timelapse_dir=str(Path(self.tmpdir.name) / "captures"),
        )
        self.service = TimelapseService(
            self.app, lambda: self.camera, self.ble, defaults
        )
        with self.app.app_context():
            db.create_all()
            self.service.ensure_schema()
            self.service.ensure_default_config()
        self.app.config["TIMELAPSE_SERVICE"] = self.service
        self.app.register_blueprint(timelapse_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.tmpdir.cleanup()

    def test_config_start_capture_and_stop_are_persisted(self):
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
            "light_enabled": True,
            "light_intensity": 42,
        })
        self.assertEqual(response.status_code, 200)

        response = self.client.post("/api/timelapse/start")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["running"])
        self.assertEqual(self.camera.start_calls, [(30, 1920, 1080)])
        self.assertTrue(self.camera.timelapse_organize_by_date)

        self.camera.callbacks["on_before_capture"]({"capture_count": 1})
        self.assertEqual(self.ble.commands, ["SET_LIGHT:42"])

        self.camera.callbacks["on_capture"]({
            "captured_at": "2026-08-06T21:00:00",
            "path": "/captures/shot.jpg",
            "capture_count": 1,
            "width": 1920,
            "height": 1080,
        })
        self.assertEqual(self.ble.commands[-1], "SET_LIGHT:0")
        with self.app.app_context():
            config = db.session.get(TimelapseConfig, 1)
            reading = SensorReading.query.one()
            self.assertEqual(config.capture_count, 1)
            self.assertEqual(config.last_capture_path, "/captures/shot.jpg")
            self.assertEqual(reading.pan_pulse_us, 1450)
            self.assertEqual(reading.tilt_pulse_us, 1520)

        response = self.client.post("/api/timelapse/stop")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["desired_running"])

    def test_saved_active_timelapse_resumes(self):
        with self.app.app_context():
            config = db.session.get(TimelapseConfig, 1)
            config.interval_seconds = 15
            config.width = 1280
            config.height = 720
            config.is_running = True
            config.auto_resume = True
            db.session.commit()
            resumed = self.service.resume_if_needed()

        self.assertTrue(resumed)
        self.assertEqual(self.camera.start_calls, [(15, 1280, 720)])

    def test_configuration_cannot_change_while_running(self):
        self.camera.running = True
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
        })
        self.assertEqual(response.status_code, 409)

    def test_stop_clears_persisted_intent_even_without_camera(self):
        with self.app.app_context():
            config = db.session.get(TimelapseConfig, 1)
            config.is_running = True
            db.session.commit()
        self.camera = UnavailableTimelapseCamera()

        response = self.client.post("/api/timelapse/stop")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["desired_running"])


class TimelapseMigrationTests(unittest.TestCase):
    def test_legacy_minutes_are_migrated_to_seconds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = Flask(__name__)
            database_path = Path(tmpdir) / "legacy.db"
            app.config.update(
                SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
                SQLALCHEMY_TRACK_MODIFICATIONS=False,
            )
            db.init_app(app)
            camera = FakeTimelapseCamera()
            defaults = SimpleNamespace(
                default_interval_seconds=10,
                auto_resume=True,
                timelapse_dir=str(Path(tmpdir) / "captures"),
            )
            service = TimelapseService(
                app,
                lambda: camera,
                SimpleNamespace(last_state={}),
                defaults,
            )
            with app.app_context():
                with db.engine.begin() as connection:
                    connection.exec_driver_sql(
                        "CREATE TABLE timelapse_config ("
                        "id INTEGER PRIMARY KEY, interval_minutes INTEGER NOT NULL, "
                        "width INTEGER NOT NULL, height INTEGER NOT NULL, "
                        "is_running BOOLEAN, updated_at DATETIME)"
                    )
                    connection.exec_driver_sql(
                        "INSERT INTO timelapse_config "
                        "(id, interval_minutes, width, height, is_running) "
                        "VALUES (1, 2, 1280, 720, 0)"
                    )
                service.ensure_schema()
                config = db.session.get(TimelapseConfig, 1)
                self.assertEqual(config.interval_seconds, 120)
                self.assertTrue(config.auto_resume)
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
