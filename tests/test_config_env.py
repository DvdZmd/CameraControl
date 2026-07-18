import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


class EnvLoadingTests(unittest.TestCase):
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
