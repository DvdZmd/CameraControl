import unittest
import subprocess
from unittest.mock import Mock, patch

from flask import Flask

from routes import admin_routes
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

    @patch("routes.admin_routes._throttled_flags", return_value={
        "raw": "0x1",
        "undervoltage_now": True,
        "undervoltage_occurred": False,
    })
    @patch("routes.admin_routes._cpu_temperature_c", return_value=54.2)
    @patch("routes.admin_routes._cpu_usage_percent", return_value=37.5)
    @patch("routes.admin_routes._storage_status", return_value={
        "total_bytes": 1000,
        "used_bytes": 400,
        "free_bytes": 600,
        "free_percent": 60.0,
    })
    def test_system_status_reports_raspberry_health(self, _storage, _usage, _temperature, _power):
        response = self.client.get("/api/admin/system-status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "cpu_temperature_c": 54.2,
            "cpu_usage_percent": 37.5,
            "power": {
                "raw": "0x1",
                "undervoltage_now": True,
                "undervoltage_occurred": False,
            },
            "storage": {
                "total_bytes": 1000,
                "used_bytes": 400,
                "free_bytes": 600,
                "free_percent": 60.0,
            },
        })

    @patch("routes.admin_routes.shutil.disk_usage")
    def test_storage_status_reports_free_space_for_timelapse_filesystem(self, disk_usage):
        disk_usage.return_value = Mock(total=1000, used=250, free=750)

        with self.client.application.test_request_context():
            status = admin_routes._storage_status()

        self.assertEqual(status, {
            "total_bytes": 1000,
            "used_bytes": 250,
            "free_bytes": 750,
            "free_percent": 75.0,
        })

    @patch("routes.admin_routes._read_cpu_sample", side_effect=[(1000, 600), (1100, 620)])
    def test_cpu_usage_uses_proc_stat_deltas(self, _sample):
        previous = admin_routes._previous_cpu_sample
        try:
            admin_routes._previous_cpu_sample = None
            self.assertIsNone(admin_routes._cpu_usage_percent())
            self.assertEqual(admin_routes._cpu_usage_percent(), 80.0)
        finally:
            admin_routes._previous_cpu_sample = previous

    def test_throttled_parser_accepts_vcgencmd_output(self):
        self.assertEqual(
            admin_routes._parse_throttled_value("throttled=0x10001\n"),
            0x10001,
        )

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
