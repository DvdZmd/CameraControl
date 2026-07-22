import unittest
import subprocess
from unittest.mock import Mock, patch

from flask import Flask

from routes.admin_routes import admin_bp


class AdminRoutesTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(admin_bp)
        self.client = app.test_client()

    def test_reboot_requires_confirmation(self):
        response = self.client.post("/api/admin/reboot", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "error")

    @patch("routes.admin_routes.threading.Thread")
    @patch("routes.admin_routes._reboot_command", return_value=["/bin/systemctl", "reboot"])
    def test_reboot_starts_background_thread(self, _reboot_command, thread_cls):
        thread = Mock()
        thread_cls.return_value = thread

        response = self.client.post("/api/admin/reboot", json={"confirm": True})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["status"], "rebooting")
        thread_cls.assert_called_once()
        _, kwargs = thread_cls.call_args
        self.assertEqual(kwargs["target"].__name__, "_run_reboot_command")
        self.assertEqual(kwargs["args"], (["/bin/systemctl", "reboot"],))
        self.assertTrue(kwargs["daemon"])
        thread.start.assert_called_once()

    @patch("routes.admin_routes.subprocess.Popen")
    @patch("routes.admin_routes.time.sleep")
    def test_run_reboot_command_uses_detached_process(self, sleep, popen):
        from routes.admin_routes import _run_reboot_command

        _run_reboot_command(["/bin/systemctl", "reboot"])

        sleep.assert_called_once_with(0.5)
        popen.assert_called_once_with(
            ["/bin/systemctl", "reboot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


if __name__ == "__main__":
    unittest.main()
