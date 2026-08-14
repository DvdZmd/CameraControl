import os
import unittest
from unittest.mock import patch

from flask import Flask

from profiles import FeatureConfig, ProjectProfile, resolve_profile
from routes.system_routes import system_bp


class ProjectProfileTests(unittest.TestCase):
    def test_default_profile_preserves_all_current_modules(self):
        profile = resolve_profile("default")

        self.assertEqual(profile.name, "default")
        self.assertEqual(profile.features.as_dict(), {
            "camera": True,
            "timelapse": True,
            "esp32": True,
            "pan_tilt": True,
            "lighting": True,
            "sensors": True,
            "tuya": True,
        })

    def test_starseek_disables_sensor_and_tuya_modules(self):
        profile = resolve_profile("starseek")

        self.assertFalse(profile.features.sensors)
        self.assertFalse(profile.features.tuya)
        self.assertTrue(profile.features.camera)
        self.assertTrue(profile.features.timelapse)
        self.assertTrue(profile.features.esp32)
        self.assertTrue(profile.features.pan_tilt)
        self.assertFalse(profile.features.lighting)

    def test_fungiforge_monitor_disables_only_pan_tilt(self):
        profile = resolve_profile("fungiforge_monitor")

        self.assertFalse(profile.features.pan_tilt)
        self.assertTrue(profile.features.esp32)
        self.assertTrue(profile.features.lighting)
        self.assertTrue(profile.features.sensors)
        self.assertTrue(profile.features.tuya)

    def test_profile_can_be_selected_from_environment(self):
        with patch.dict(os.environ, {"CAMERACONTROL_PROFILE": "StarSeek"}):
            self.assertEqual(resolve_profile().name, "starseek")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Perfil CameraControl desconocido"):
            resolve_profile("no-existe")

    def test_invalid_dependencies_are_rejected(self):
        profile = ProjectProfile(
            "invalid",
            FeatureConfig(camera=False, timelapse=True),
        )

        with self.assertRaisesRegex(ValueError, "timelapse requiere camera"):
            profile.validate()

    def test_esp32_subcapabilities_require_transport(self):
        for feature_name in ("pan_tilt", "lighting"):
            values = {"esp32": False, feature_name: True}
            profile = ProjectProfile("invalid", FeatureConfig(**values))
            with self.subTest(feature=feature_name):
                with self.assertRaisesRegex(ValueError, f"{feature_name} requiere esp32"):
                    profile.validate()

    def test_capabilities_endpoint_exposes_active_contract(self):
        app = Flask(__name__)
        app.config["PROJECT_PROFILE"] = resolve_profile("starseek")
        app.register_blueprint(system_bp)

        response = app.test_client().get("/api/system/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "api_version": "1",
            "profile": "starseek",
            "features": {
                "camera": True,
                "timelapse": True,
                "esp32": True,
                "pan_tilt": True,
                "lighting": False,
                "sensors": False,
                "tuya": False,
            },
        })


if __name__ == "__main__":
    unittest.main()
