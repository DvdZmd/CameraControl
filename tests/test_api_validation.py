import unittest
import sys
from types import ModuleType

from flask import Flask


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
from routes.esp32_routes import esp32_bp


class FakeCamera:
    def __init__(self):
        self.calls = []

    def apply_preset(self, preset):
        self.calls.append(("preset", preset))
        return True

    def take_custom_photo(self, width, height):
        self.calls.append(("photo", width, height))
        return b"jpeg"

    def get_capabilities(self):
        return {"af_supported": False}

    def set_resolution(self, width, height):
        self.calls.append(("resolution", width, height))

    def set_rotation(self, rotation):
        self.calls.append(("rotation", rotation))

    def start_timelapse(self, interval, width, height):
        self.calls.append(("timelapse", interval, width, height))

    def stop_timelapse(self):
        self.calls.append(("stop_timelapse",))

    def update_control(self, name, value):
        self.calls.append(("control", name, value))


class FakeBleController:
    def __init__(self):
        self.commands = []

    def send_command_sync(self, command):
        self.commands.append(command)
        return {"ok": True, "command": command}

    def set_speed_sync(self, mode):
        self.commands.append(f"SET_SPEED:{mode}")
        return {"ok": True}


class ApiValidationTests(unittest.TestCase):
    def setUp(self):
        self.camera = FakeCamera()
        self.previous_camera = camera_routes.rpicamz
        camera_routes.rpicamz = self.camera

        app = Flask(__name__)
        app.config["TESTING"] = True
        self.ble = FakeBleController()
        app.config["BLE_CAMERA_CONTROLLER"] = self.ble
        app.register_blueprint(camera_bp)
        app.register_blueprint(esp32_bp)
        self.client = app.test_client()

    def tearDown(self):
        camera_routes.rpicamz = self.previous_camera

    def test_camera_rejects_non_object_json(self):
        response = self.client.post("/api/camera/update_settings", json=[])
        self.assertEqual(response.status_code, 400)

    def test_camera_requires_both_resolution_dimensions(self):
        response = self.client.post("/api/camera/update_settings", json={"width": 1280})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.camera.calls, [])

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

    def test_esp32_rejects_boolean_speed(self):
        response = self.client.post("/api/esp32/speed", json={"mode": True})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
