import tempfile
import time
import unittest
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from flask import Flask

from database.models import (
    SensorLoggingSettings,
    SensorReading,
    TimelapseConfig,
    TimelapseFolder,
    db,
)
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


class LegacyTimelapseCamera:
    def __init__(self):
        self.save_path = None
        self.timelapse_organize_by_date = False
        self.timelapse_active = False
        self.capture_calls = []

    def start_timelapse(self, interval, width, height):
        raise AssertionError("El worker legacy de rpicam-z no debe iniciarse")

    def stop_timelapse(self):
        return True

    def take_custom_photo(self, width, height):
        self.capture_calls.append((width, height))
        return b"legacy-jpeg"


class PartialCallbackTimelapseCamera(LegacyTimelapseCamera):
    def start_timelapse(
        self, interval, width, height,
        on_capture=None, on_error=None, on_complete=None,
    ):
        raise AssertionError("No debe usarse sin on_before_capture")

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
            "folder_name": "cultivo agosto",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["light_warmup_seconds"], 3)

        response = self.client.post("/api/timelapse/start")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["running"])
        self.assertEqual(self.camera.start_calls, [(30, 1920, 1080)])
        self.assertTrue(self.camera.timelapse_organize_by_date)
        self.assertEqual(
            Path(self.camera.save_path),
            Path(self.tmpdir.name) / "captures" / "cultivo agosto",
        )

        with mock.patch("timelapse.service.time.sleep") as sleep:
            self.camera.callbacks["on_before_capture"]({"capture_count": 1})
        sleep.assert_called_once_with(3)
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
            self.assertEqual(config.light_warmup_seconds, 3)
            self.assertEqual(config.capture_count, 1)
            self.assertEqual(config.last_capture_path, "/captures/shot.jpg")
            self.assertEqual(
                config.last_capture_at,
                datetime(2026, 8, 7, 0, 0),
            )
            self.assertEqual(reading.pan_pulse_us, 1450)
            self.assertEqual(reading.tilt_pulse_us, 1520)
            self.assertEqual(reading.timelapse_folder.folder_name, "cultivo agosto")
            self.assertEqual(TimelapseFolder.query.count(), 1)

        response = self.client.post("/api/timelapse/stop")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["desired_running"])

    def test_timelapse_flag_is_independent_from_periodic_logger_flag(self):
        with self.app.app_context():
            db.session.add(SensorLoggingSettings(
                id=1,
                enabled=False,
                interval_seconds=60,
            ))
            db.session.commit()

        self.client.post("/api/timelapse/start")
        self.camera.callbacks["on_capture"]({
            "captured_at": "2026-08-06T21:00:00",
            "path": "/captures/shot.jpg",
            "capture_count": 1,
        })

        with self.app.app_context():
            self.assertEqual(SensorReading.query.count(), 1)

    def test_capture_does_not_persist_telemetry_when_disabled(self):
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
            "folder_name": "sin-telemetria",
            "save_sensor_readings": False,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["save_sensor_readings"])

        self.client.post("/api/timelapse/start")
        self.camera.callbacks["on_capture"]({
            "captured_at": "2026-08-06T21:00:00",
            "path": "/captures/shot.jpg",
            "capture_count": 1,
        })

        with self.app.app_context():
            self.assertEqual(SensorReading.query.count(), 0)
            self.assertEqual(TimelapseFolder.query.count(), 0)

    def test_rejects_non_boolean_sensor_reading_flag(self):
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
            "save_sensor_readings": "false",
        })
        self.assertEqual(response.status_code, 400)

    def test_lists_and_downloads_captures_inside_selected_folder(self):
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
            "light_enabled": False,
            "light_intensity": 100,
            "folder_name": "prueba-01",
        })
        self.assertEqual(response.status_code, 200)
        folder = Path(self.tmpdir.name) / "captures" / "prueba-01"
        nested = folder / "2026-08-07" / "10-00-00"
        nested.mkdir(parents=True)
        (nested / "shot_01.jpg").write_bytes(b"jpeg-one")
        (nested / "shot_02.jpg").write_bytes(b"jpeg-two")
        (nested / "ignore.txt").write_text("not a capture", encoding="utf-8")

        folders = self.client.get("/api/timelapse/folders").get_json()
        self.assertEqual(folders["folders"], ["default", "prueba-01"])

        captures_response = self.client.get(
            "/api/timelapse/captures?folder=prueba-01"
        )
        self.assertEqual(captures_response.status_code, 200)
        captures = captures_response.get_json()["captures"]
        self.assertEqual(len(captures), 2)

        single = self.client.get(
            "/api/timelapse/capture/download",
            query_string={"folder": "prueba-01", "path": captures[0]["path"]},
        )
        self.assertEqual(single.status_code, 200)
        self.assertIn(single.data, {b"jpeg-one", b"jpeg-two"})
        single.close()

        archive = self.client.post("/api/timelapse/captures/download", json={
            "folder": "prueba-01",
            "captures": [capture["path"] for capture in captures],
        })
        self.assertEqual(archive.status_code, 200)
        with zipfile.ZipFile(BytesIO(archive.data)) as downloaded:
            self.assertEqual(len(downloaded.namelist()), 2)
        archive.close()

    def test_rejects_folder_and_capture_path_traversal(self):
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
            "folder_name": "../escape",
        })
        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/api/timelapse/capture/download",
            query_string={"folder": "default", "path": "../../etc/passwd"},
        )
        self.assertIn(response.status_code, {400, 404})

    def test_deletes_selected_captures_and_complete_folder(self):
        folder = self.service.folder_path("delete-me", create=True)
        first = folder / "first.jpg"
        second = folder / "second.jpg"
        first.write_bytes(b"one")
        second.write_bytes(b"two")

        response = self.client.delete("/api/timelapse/captures", json={
            "folder": "delete-me",
            "captures": ["first.jpg"],
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())

        response = self.client.delete("/api/timelapse/folders/delete-me")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(folder.exists())

    def test_cannot_delete_folder_used_by_running_timelapse(self):
        with self.app.app_context():
            config = db.session.get(TimelapseConfig, 1)
            config.folder_name = "active"
            db.session.commit()
        self.service.folder_path("active", create=True)
        self.camera.running = True

        response = self.client.delete("/api/timelapse/folders/active")

        self.assertEqual(response.status_code, 409)

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

    def test_legacy_rpicam_z_uses_compatibility_worker_with_callbacks(self):
        legacy_camera = LegacyTimelapseCamera()
        self.camera = legacy_camera
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 3,
            "width": 1280,
            "height": 720,
            "auto_resume": True,
            "light_enabled": True,
            "light_intensity": 35,
            "light_warmup_seconds": 0,
            "folder_name": "legacy",
        })
        self.assertEqual(response.status_code, 200)

        response = self.client.post("/api/timelapse/start")
        self.assertEqual(response.status_code, 200)
        deadline = time.monotonic() + 2
        persisted_count = 0
        while persisted_count < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
            with self.app.app_context():
                persisted_count = db.session.get(TimelapseConfig, 1).capture_count
        self.assertEqual(legacy_camera.capture_calls, [(1280, 720)])
        self.assertEqual(persisted_count, 1)

        response = self.client.post("/api/timelapse/stop")
        self.assertEqual(response.status_code, 200)
        captures = list(
            (Path(self.tmpdir.name) / "captures" / "legacy").rglob("*.jpg")
        )
        self.assertEqual(len(captures), 1)
        self.assertEqual(captures[0].read_bytes(), b"legacy-jpeg")
        self.assertRegex(
            captures[0].name,
            r"^\d{4}_\d{2}_\d{2}_\d{2}-\d{2}-\d{2}\.jpg$",
        )

    def test_partial_callback_api_also_uses_compatibility_worker(self):
        camera = PartialCallbackTimelapseCamera()
        self.assertFalse(self.service._supports_native_callbacks(camera))

    def test_configuration_cannot_change_while_running(self):
        self.camera.running = True
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 30,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
        })
        self.assertEqual(response.status_code, 409)

    def test_light_requires_three_second_interval(self):
        response = self.client.put("/api/timelapse/config", json={
            "interval_seconds": 2,
            "width": 1920,
            "height": 1080,
            "auto_resume": True,
            "light_enabled": True,
            "light_intensity": 50,
            "folder_name": "minimum-light",
        })
        self.assertEqual(response.status_code, 400)

    def test_light_waits_before_capture_callback_returns(self):
        with self.app.app_context():
            self.service.configure(
                interval_seconds=3,
                width=1920,
                height=1080,
                auto_resume=True,
                light_enabled=True,
                light_intensity=50,
                light_warmup_seconds=3,
                folder_name="warmup",
            )
        with mock.patch("timelapse.service.time.sleep") as sleep:
            self.service._on_before_capture({"capture_count": 1})
        sleep.assert_called_once_with(3)
        self.assertEqual(self.ble.commands[-1], "SET_LIGHT:50")

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
