import unittest
import sys
from types import ModuleType

from flask import Flask
from database.models import CameraSettings, Esp32Settings, db


class BootstrapCamera:
    pass


fake_rpicam_module = ModuleType("rpicam_z.rpicam_z")
fake_rpicam_module.CAMERA_IMPORT_ERROR = None
fake_rpicam_module.UnavailableCamera = BootstrapCamera
fake_rpicam_module.rpicam_z = BootstrapCamera
fake_rpicam_package = ModuleType("rpicam_z")
fake_rpicam_package.rpicam_z = fake_rpicam_module
sys.modules.setdefault("rpicam_z", fake_rpicam_package)
sys.modules.setdefault("rpicam_z.rpicam_z", fake_rpicam_module)

from routes import camera_routes
from routes.camera_routes import camera_bp
from routes.esp32_routes import esp32_bp, lighting_bp, pan_tilt_bp


class FakeCamera:
    def __init__(self):
        self.calls = []
        self.current_width = 1280
        self.current_height = 720
        self.current_rotation = 0
        self.pipeline_rotation = 0
        self.display_rotation = 0
        self.max_sensor_res = (4608, 2592)
        self.af_supported = False
        self.controls = {
            "Brightness": 0.0,
            "Contrast": 1.0,
            "Saturation": 1.0,
            "AeEnable": True,
        }
        self.closed = False

    def apply_preset(self, preset):
        self.calls.append(("preset", preset))
        self.controls["Contrast"] = 1.5
        return True

    def take_custom_photo(self, width, height):
        self.calls.append(("photo", width, height))
        return b"jpeg"

    def get_capabilities(self):
        return {
            "max_width": self.max_sensor_res[0],
            "max_height": self.max_sensor_res[1],
            "af_supported": self.af_supported,
            "current_width": self.current_width,
            "current_height": self.current_height,
            "current_rotation": self.current_rotation,
            "pipeline_rotation": self.pipeline_rotation,
            "display_rotation": self.display_rotation,
            "supported_pipeline_rotations": [0, 180],
        }

    def set_resolution(self, width, height):
        self.current_width = width
        self.current_height = height
        self.calls.append(("resolution", width, height))

    def set_rotation(self, rotation):
        self.current_rotation = rotation
        self.pipeline_rotation = rotation if rotation in {0, 180} else 0
        self.display_rotation = (rotation - self.pipeline_rotation) % 360
        self.calls.append(("rotation", rotation))
        return True

    def start_timelapse(self, interval, width, height):
        self.calls.append(("timelapse", interval, width, height))

    def stop_timelapse(self):
        self.calls.append(("stop_timelapse",))

    def update_control(self, name, value):
        self.controls[name] = value
        self.calls.append(("control", name, value))
        return True

    def get_frame_packet(self):
        return {"jpeg_bytes": b"jpeg"}

    def close(self):
        self.closed = True
        self.calls.append(("close",))


class FakeBleController:
    def __init__(self):
        self.commands = []
        self.last_state = {"P": "1450", "T": "1500", "S": "2"}

    def send_command_sync(self, command):
        self.commands.append(command)
        return {"ok": True, "command": command}

    def set_speed_sync(self, mode):
        self.commands.append(f"SET_SPEED:{mode}")
        return {"ok": True}

    def get_status_sync(self):
        return {
            "connected": True,
            "address": "AA:BB:CC:DD:EE:FF",
            "device_name": "ESP32-CameraHead",
            "last_state": self.last_state,
        }


class ApiValidationTests(unittest.TestCase):
    def setUp(self):
        self.camera = FakeCamera()
        self.previous_camera = camera_routes.rpicamz
        self.previous_camera_initialized = camera_routes.camera_initialized
        self.previous_stream_enabled = camera_routes.stream_enabled
        self.previous_camera_closed_by_user = camera_routes.camera_closed_by_user
        camera_routes.rpicamz = self.camera
        camera_routes.camera_initialized = True
        camera_routes.stream_enabled = False
        camera_routes.camera_closed_by_user = False

        app = Flask(__name__)
        app.config["TESTING"] = True
        self.ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = self.ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        app.register_blueprint(camera_bp)
        app.register_blueprint(esp32_bp)
        app.register_blueprint(pan_tilt_bp)
        app.register_blueprint(lighting_bp)
        self.client = app.test_client()

    def tearDown(self):
        camera_routes.rpicamz = self.previous_camera
        camera_routes.camera_initialized = self.previous_camera_initialized
        camera_routes.stream_enabled = self.previous_stream_enabled
        camera_routes.camera_closed_by_user = self.previous_camera_closed_by_user

    def test_camera_rejects_non_object_json(self):
        response = self.client.post("/api/camera/update_settings", json=[])
        self.assertEqual(response.status_code, 400)

    def test_camera_requires_both_resolution_dimensions(self):
        response = self.client.post("/api/camera/update_settings", json={"width": 1280})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.camera.calls, [])

    def test_custom_photo_download_uses_identifiable_timestamp_name(self):
        response = self.client.get("/api/camera/take_photo_custom?w=1920&h=1080")
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.headers["Content-Disposition"],
            r'filename="?\d{4}_\d{2}_\d{2}_\d{2}-\d{2}-\d{2}\.jpg"?',
        )

    def test_camera_rejects_out_of_range_control(self):
        response = self.client.post("/api/camera/update_settings", json={"Brightness": 2})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.camera.calls, [])

    def test_camera_validates_complete_payload_before_hardware_access(self):
        response = self.client.post(
            "/api/camera/update_settings",
            json={"width": 1280, "height": 720, "Brightness": 2},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.camera.calls, [])

    def test_camera_rejects_unknown_settings(self):
        response = self.client.post("/api/camera/update_settings", json={"brightness": 0.2})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.camera.calls, [])

    def test_camera_accepts_valid_settings(self):
        response = self.client.post(
            "/api/camera/update_settings",
            json={"width": 1280, "height": 720, "Brightness": 0.2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(("resolution", 1280, 720), self.camera.calls)
        self.assertIn(("control", "Brightness", 0.2), self.camera.calls)

    def test_manual_focus_forces_manual_mode_before_lens_position(self):
        self.camera.af_supported = True

        response = self.client.post(
            "/api/camera/update_settings",
            json={"LensPosition": 4.5},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.camera.calls,
            [("control", "AfMode", 0), ("control", "LensPosition", 4.5)],
        )
        self.assertEqual(self.camera.controls["AfMode"], 0)

    def test_single_autofocus_mode_starts_autofocus_cycle(self):
        self.camera.af_supported = True

        response = self.client.post(
            "/api/camera/update_settings",
            json={"AfMode": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.camera.calls,
            [("control", "AfMode", 1), ("control", "AfTrigger", 0)],
        )

    def test_camera_reports_rejected_control(self):
        def reject_control(name, value):
            self.camera.calls.append(("control", name, value))
            return False

        self.camera.update_control = reject_control

        response = self.client.post(
            "/api/camera/update_settings",
            json={"Brightness": 0.2},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("rechazó el control", response.get_json()["message"])

    def test_camera_status_reports_stream_disabled_by_default(self):
        response = self.client.get("/api/camera/camera_status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["stream_enabled"])

    def test_video_feed_requires_stream_enabled(self):
        response = self.client.get("/api/camera/video_feed")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["message"], "Streaming de cámara apagado")

    def test_camera_stream_start_and_stop_toggle_backend_state(self):
        start_response = self.client.post("/api/camera/stream/start")
        self.assertEqual(start_response.status_code, 200)
        self.assertTrue(start_response.get_json()["stream_enabled"])
        self.assertTrue(camera_routes.stream_enabled)

        stop_response = self.client.post("/api/camera/stream/stop")
        self.assertEqual(stop_response.status_code, 200)
        self.assertFalse(stop_response.get_json()["stream_enabled"])
        self.assertFalse(camera_routes.stream_enabled)
        self.assertNotIn(("close",), self.camera.calls)
        self.assertNotIn(("stop_timelapse",), self.camera.calls)

        photo_response = self.client.get(
            "/api/camera/take_photo_custom?w=1280&h=720"
        )
        self.assertEqual(photo_response.status_code, 200)
        self.assertIn(("photo", 1280, 720), self.camera.calls)

    def test_camera_stream_start_returns_503_when_camera_is_unavailable(self):
        previous_factory = camera_routes.rpicam_z

        class FailingCamera:
            def __init__(self):
                raise RuntimeError("no camera")

        camera_routes.rpicam_z = FailingCamera
        camera_routes.rpicamz = camera_routes._LocalUnavailableCamera(RuntimeError("no camera"))
        try:
            response = self.client.post("/api/camera/stream/start")
        finally:
            camera_routes.rpicam_z = previous_factory

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["stream_enabled"])
        self.assertFalse(camera_routes.stream_enabled)

    def test_camera_initialization_is_explicit_and_idempotent(self):
        previous_factory = camera_routes.rpicam_z
        created = []

        class InitializedCamera(FakeCamera):
            def __init__(self):
                super().__init__()
                created.append(self)

        camera_routes.rpicam_z = InitializedCamera
        camera_routes.camera_initialized = False
        try:
            first = camera_routes.initialize_camera()
            second = camera_routes.initialize_camera()
        finally:
            camera_routes.rpicam_z = previous_factory

        self.assertIs(first, second)
        self.assertEqual(created, [first])
        self.assertTrue(camera_routes.camera_initialized)

    def test_camera_persists_applied_settings_when_database_is_available(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)
        app.register_blueprint(camera_bp)

        with app.app_context():
            db.create_all()

        client = app.test_client()
        response = client.post(
            "/api/camera/update_settings",
            json={"width": 1920, "height": 1080, "rotation": 90, "AeEnable": False},
        )

        self.assertEqual(response.status_code, 200)
        with app.app_context():
            saved = CameraSettings.query.one()
            self.assertEqual(saved.width, 1920)
            self.assertEqual(saved.height, 1080)
            self.assertEqual(saved.rotation, 90)
            self.assertEqual(saved.pipeline_rotation, 0)
            self.assertEqual(saved.display_rotation, 90)
            self.assertFalse(saved.controls["AeEnable"])

        self.assertIn(("rotation", 90), self.camera.calls)

        status = client.get("/api/camera/camera_status").get_json()
        self.assertEqual(status["current_width"], 1920)
        self.assertEqual(status["current_height"], 1080)
        self.assertEqual(status["current_rotation"], 90)
        self.assertEqual(status["pipeline_rotation"], 0)
        self.assertEqual(status["display_rotation"], 90)
        self.assertFalse(status["controls"]["AeEnable"])
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_camera_applies_saved_settings_on_startup(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)

        with app.app_context():
            db.create_all()
            db.session.add(CameraSettings(
                camera_key="unknown:4608x2592:af=0",
                max_width=4608,
                max_height=2592,
                af_supported=False,
                width=1640,
                height=1232,
                rotation=270,
                pipeline_rotation=0,
                display_rotation=270,
                controls={"Brightness": 0.4, "AeEnable": False, "AfMode": 2},
            ))
            db.session.commit()

            applied = camera_routes.apply_saved_camera_settings(app.logger)

        self.assertTrue(applied)
        self.assertIn(("resolution", 1640, 1232), self.camera.calls)
        self.assertIn(("control", "Brightness", 0.4), self.camera.calls)
        self.assertIn(("control", "AeEnable", False), self.camera.calls)
        self.assertNotIn(("control", "AfMode", 2), self.camera.calls)
        self.assertIn(("rotation", 270), self.camera.calls)
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_rejects_invalid_set_speed_command(self):
        response = self.client.post("/api/esp32/command", json={"command": "SET_SPEED:99"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.ble.commands, [])

    def test_esp32_rejects_three_axis_set_abs(self):
        response = self.client.post(
            "/api/esp32/command",
            json={"command": "SET_ABS:1450,1450,1450"},
        )
        self.assertEqual(response.status_code, 400)

    def test_esp32_accepts_fungi_absolute_position(self):
        response = self.client.post(
            "/api/esp32/command",
            json={"command": "SET_ABS:1450,1500"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ble.commands, ["SET_ABS:1450,1500"])

    def test_esp32_light_turns_on(self):
        response = self.client.post("/api/esp32/light", json={"on": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["light_on"])
        self.assertEqual(response.get_json()["intensity"], 100)
        self.assertEqual(self.ble.commands, ["LIGHT_ON"])
        self.assertEqual(self.ble.last_state["L"], "100")

    def test_esp32_light_turns_off(self):
        response = self.client.post("/api/esp32/light", json={"on": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["light_on"])
        self.assertEqual(self.ble.commands, ["LIGHT_OFF"])

    def test_esp32_light_rejects_non_boolean_state(self):
        response = self.client.post("/api/esp32/light", json={"on": 1})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.ble.commands, [])

    def test_esp32_sets_light_pwm_intensity(self):
        response = self.client.post("/api/esp32/light", json={"intensity": 37})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["intensity"], 37)
        self.assertTrue(response.get_json()["light_on"])
        self.assertEqual(self.ble.commands, ["SET_LIGHT:37"])
        self.assertEqual(self.ble.last_state["L"], "37")

    def test_esp32_restores_saved_intensity_after_turning_off(self):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            BLE_CAMERA_CONTROLLER=self.ble,
            FEATURES={"pan_tilt": True, "lighting": True},
        )
        db.init_app(app)
        app.register_blueprint(esp32_bp)
        app.register_blueprint(lighting_bp)
        with app.app_context():
            db.create_all()
        client = app.test_client()

        response = client.post("/api/esp32/light", json={"intensity": 37})
        self.assertEqual(response.status_code, 200)
        response = client.post("/api/esp32/light", json={"on": False})
        self.assertEqual(response.status_code, 200)

        status = client.get("/api/esp32/status").get_json()
        self.assertEqual(status["saved_light"], {
            "light_on": False,
            "intensity": 37,
        })

        response = client.post("/api/esp32/light", json={"on": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["intensity"], 37)
        self.assertEqual(
            self.ble.commands,
            ["SET_LIGHT:37", "LIGHT_OFF", "SET_LIGHT:37"],
        )
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_accepts_valid_manual_light_pwm_command(self):
        response = self.client.post(
            "/api/esp32/command",
            json={"command": "SET_LIGHT:75"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ble.commands, ["SET_LIGHT:75"])

    def test_manual_command_cannot_bypass_disabled_lighting_feature(self):
        self.client.application.config["FEATURES"]["lighting"] = False

        response = self.client.post(
            "/api/esp32/command",
            json={"command": "SET_LIGHT:75"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.ble.commands, [])

    def test_esp32_rejects_invalid_light_pwm_intensity(self):
        for intensity in (-1, 101, True, 12.5):
            response = self.client.post(
                "/api/esp32/light",
                json={"intensity": intensity},
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.ble.commands, [])

    def test_esp32_rejects_boolean_speed(self):
        response = self.client.post("/api/esp32/speed", json={"mode": True})
        self.assertEqual(response.status_code, 400)

    def test_esp32_persists_speed_mode(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        db.init_app(app)
        app.register_blueprint(esp32_bp)
        app.register_blueprint(pan_tilt_bp)

        with app.app_context():
            db.create_all()

        client = app.test_client()
        response = client.post("/api/esp32/speed", json={"mode": 4})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["saved_speed_mode"], 4)
        self.assertEqual(response.get_json()["current_speed_mode"], 4)
        self.assertEqual(ble.commands, ["SET_SPEED:4"])
        self.assertEqual(ble.last_state["S"], "4")
        with app.app_context():
            saved = db.session.get(Esp32Settings, 1)
            self.assertEqual(saved.speed_mode, 4)
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_status_includes_saved_speed_mode(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        db.init_app(app)
        app.register_blueprint(esp32_bp)

        with app.app_context():
            db.create_all()
            db.session.add(Esp32Settings(id=1, speed_mode=3))
            db.session.commit()

        client = app.test_client()
        response = client.get("/api/esp32/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["saved_speed_mode"], 3)
        self.assertEqual(
            response.get_json()["current_position"],
            {
                "pan": {"pulse_us": 1450, "angle_deg": 90.0},
                "tilt": {"pulse_us": 1500, "angle_deg": 94.7},
            },
        )
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_status_includes_saved_position_details(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        db.init_app(app)
        app.register_blueprint(esp32_bp)

        with app.app_context():
            db.create_all()
            db.session.add(Esp32Settings(
                id=1,
                custom_pan_pulse=1450,
                custom_tilt_pulse=1500,
            ))
            db.session.commit()

        client = app.test_client()
        response = client.get("/api/esp32/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["saved_position_details"],
            {
                "pan": {"pulse_us": 1450, "angle_deg": 90.0},
                "tilt": {"pulse_us": 1500, "angle_deg": 94.7},
            },
        )
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_saves_current_position_from_telemetry(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        db.init_app(app)
        app.register_blueprint(esp32_bp)
        app.register_blueprint(pan_tilt_bp)

        with app.app_context():
            db.create_all()

        client = app.test_client()
        response = client.post("/api/esp32/position/current")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["saved_position"], {"pan": 1450, "tilt": 1500})
        with app.app_context():
            saved = db.session.get(Esp32Settings, 1)
            self.assertEqual(saved.custom_pan_pulse, 1450)
            self.assertEqual(saved.custom_tilt_pulse, 1500)
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_returns_to_saved_position(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        db.init_app(app)
        app.register_blueprint(esp32_bp)
        app.register_blueprint(pan_tilt_bp)

        with app.app_context():
            db.create_all()
            db.session.add(Esp32Settings(
                id=1,
                custom_pan_pulse=1600,
                custom_tilt_pulse=1400,
            ))
            db.session.commit()

        client = app.test_client()
        response = client.post("/api/esp32/position/return")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ble.commands, ["SET_ABS:1600,1400"])
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_esp32_return_requires_saved_position(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = ble
        app.config["FEATURES"] = {"pan_tilt": True, "lighting": True}
        db.init_app(app)
        app.register_blueprint(esp32_bp)
        app.register_blueprint(pan_tilt_bp)

        with app.app_context():
            db.create_all()

        client = app.test_client()
        response = client.post("/api/esp32/position/return")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ble.commands, [])
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
