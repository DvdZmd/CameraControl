import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import AppConfig, InstanceConfig, PROJECT_ROOT, TuyaConfig


class EnvLoadingTests(unittest.TestCase):
    def test_default_instance_preserves_legacy_paths(self):
        with patch.dict(os.environ, {}, clear=True):
            instance = InstanceConfig.from_env()

        self.assertEqual(instance.name, "default")
        self.assertEqual(instance.database_path, PROJECT_ROOT / "database" / "app.db")
        self.assertEqual(instance.timelapse_dir, PROJECT_ROOT / "timelapse")
        self.assertEqual(instance.log_path, PROJECT_ROOT / "logs" / "server.log")

    def test_named_instances_resolve_isolated_paths(self):
        with patch.dict(
            os.environ,
            {"CAMERACONTROL_INSTANCE": "observatorio"},
            clear=True,
        ):
            observatory = InstanceConfig.from_env()
        with patch.dict(
            os.environ,
            {"CAMERACONTROL_INSTANCE": "cultivo_garage"},
            clear=True,
        ):
            cultivation = InstanceConfig.from_env()

        self.assertEqual(
            observatory.database_path,
            PROJECT_ROOT / "data" / "observatorio" / "app.db",
        )
        self.assertEqual(
            cultivation.database_path,
            PROJECT_ROOT / "data" / "cultivo_garage" / "app.db",
        )
        self.assertNotEqual(observatory.database_path, cultivation.database_path)
        self.assertNotEqual(observatory.timelapse_dir, cultivation.timelapse_dir)

    def test_instance_path_overrides_have_precedence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            environment = {
                "CAMERACONTROL_INSTANCE": "observatorio",
                "CAMERACONTROL_DATA_DIR": str(root / "instances"),
                "DATABASE_PATH": str(root / "custom.db"),
                "TIMELAPSE_DIR": str(root / "captures"),
                "LOG_FILE_PATH": str(root / "custom.log"),
            }
            with patch.dict(os.environ, environment, clear=True):
                instance = InstanceConfig.from_env()

            self.assertEqual(instance.data_dir, root / "instances" / "observatorio")
            self.assertEqual(instance.database_path, root / "custom.db")
            self.assertEqual(instance.timelapse_dir, root / "captures")
            self.assertEqual(instance.log_path, root / "custom.log")

    def test_blank_path_overrides_are_treated_as_unset(self):
        with patch.dict(
            os.environ,
            {
                "CAMERACONTROL_INSTANCE": "observatorio",
                "CAMERACONTROL_DATA_DIR": "",
                "DATABASE_PATH": "",
                "TIMELAPSE_DIR": "",
                "LOG_FILE_PATH": "",
            },
            clear=True,
        ):
            instance = InstanceConfig.from_env()

        expected_root = PROJECT_ROOT / "data" / "observatorio"
        self.assertEqual(instance.database_path, expected_root / "app.db")
        self.assertEqual(instance.timelapse_dir, expected_root / "timelapse")
        self.assertEqual(instance.log_path, expected_root / "logs" / "server.log")

    def test_instance_name_rejects_path_traversal(self):
        invalid_names = ("../otro", "cultivo/uno", "/tmp/data", "Mayusculas")
        for name in invalid_names:
            with self.subTest(name=name):
                with patch.dict(
                    os.environ,
                    {"CAMERACONTROL_INSTANCE": name},
                    clear=True,
                ):
                    with self.assertRaisesRegex(ValueError, "CAMERACONTROL_INSTANCE"):
                        InstanceConfig.from_env()

    def test_instance_creates_only_resolved_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch.dict(
                os.environ,
                {
                    "CAMERACONTROL_INSTANCE": "cultivo",
                    "CAMERACONTROL_DATA_DIR": str(root),
                },
                clear=True,
            ):
                instance = InstanceConfig.from_env()
            instance.ensure_directories()

            self.assertTrue(instance.database_path.parent.is_dir())
            self.assertTrue(instance.timelapse_dir.is_dir())
            self.assertTrue(instance.log_path.parent.is_dir())
            self.assertFalse(instance.database_path.exists())
            self.assertFalse(instance.log_path.exists())

    def test_app_config_uses_instance_paths_for_services(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                os.environ,
                {
                    "CAMERACONTROL_INSTANCE": "starseek_pi",
                    "CAMERACONTROL_DATA_DIR": tmpdir,
                },
                clear=True,
            ):
                config = AppConfig()

        self.assertEqual(config.logging.file_path, str(config.instance.log_path))
        self.assertEqual(
            config.timelapse.timelapse_dir,
            str(config.instance.timelapse_dir),
        )

    def test_tuya_config_reads_environment_for_each_instance(self):
        with patch.dict(os.environ, {"TUYA_API_KEY": "first-key"}):
            first = TuyaConfig()
            os.environ["TUYA_API_KEY"] = "second-key"
            second = TuyaConfig()

        self.assertEqual(first.api_key, "first-key")
        self.assertEqual(second.api_key, "second-key")

    def test_tuya_config_repr_does_not_expose_sensitive_values(self):
        sensitive_values = {
            "TUYA_API_KEY": "visible-key-must-not-leak",
            "TUYA_API_SECRET": "secret-must-not-leak",
            "TUYA_DEVICE_ID": "device-must-not-leak",
            "TUYA_USERNAME": "user-must-not-leak",
            "TUYA_PASSWORD": "password-must-not-leak",
        }
        with patch.dict(os.environ, sensitive_values):
            representation = repr(TuyaConfig())

        for value in sensitive_values.values():
            self.assertNotIn(value, representation)
        self.assertIn("api_endpoint=", representation)
        self.assertIn("country_code=", representation)

    def test_app_config_has_no_inactive_camera_configuration(self):
        self.assertFalse(hasattr(AppConfig(), "camera"))

    def test_tuya_config_loads_env_from_project_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".env").write_text(
                "TUYA_API_KEY=test-key\n"
                "TUYA_API_SECRET=test-secret\n"
                "TUYA_USERNAME=test-user\n"
                "TUYA_PASSWORD=test-pass\n"
                "TUYA_COUNTRY_CODE=54\n"
                "TUYA_SCHEMA=smartlife\n",
                encoding="utf-8",
            )

            project_root = Path(__file__).resolve().parents[1]
            (tmp_path / "config.py").write_text(
                (project_root / "config.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            sys.path.insert(0, str(tmp_path))
            sys.modules.pop("config", None)
            try:
                spec = importlib.util.spec_from_file_location("config", tmp_path / "config.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules["config"] = module
                spec.loader.exec_module(module)

                tuya_config = module.TuyaConfig()
                self.assertEqual(tuya_config.api_key, "test-key")
                self.assertEqual(tuya_config.api_secret, "test-secret")
                self.assertEqual(tuya_config.username, "test-user")
                self.assertEqual(tuya_config.password, "test-pass")
                self.assertEqual(tuya_config.country_code, "54")
                self.assertEqual(tuya_config.schema, "smartlife")
            finally:
                sys.modules.pop("config", None)
                sys.path.remove(str(tmp_path))


if __name__ == "__main__":
    unittest.main()
