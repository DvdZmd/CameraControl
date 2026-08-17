import unittest
from pathlib import Path

from flask import Flask, render_template

from profiles import resolve_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DashboardTemplateTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(PROJECT_ROOT / "templates"),
        )

    def _render_status_bar(self, profile_name):
        profile = resolve_profile(profile_name).as_dict()
        profile["instance"] = "test-instance"
        with self.app.test_request_context():
            return render_template(
                "components/layout/top-bar.html",
                camera_control=profile,
            )

    def test_home_exposes_operational_identity_and_manual_refresh(self):
        rendered = self._render_status_bar("default")

        self.assertIn('id="home-profile-name"', rendered)
        self.assertIn('id="home-instance-name"', rendered)
        self.assertIn('id="home-api-version"', rendered)
        self.assertIn('data-action="refresh-dashboard-status"', rendered)
        self.assertIn('id="operational-status"', rendered)
        self.assertIn("test-instance", rendered)

    def test_home_marks_profile_features_without_hiding_disabled_ones(self):
        rendered = self._render_status_bar("starseek")

        self.assertIn("home-feature-chip enabled", rendered)
        self.assertIn("home-feature-chip disabled", rendered)
        self.assertIn("tuya", rendered)
        self.assertIn("sensors", rendered)

    def test_home_javascript_does_not_call_tuya(self):
        source = (PROJECT_ROOT / "static/js/components/home.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("/api/tuya", source)
        self.assertNotIn("setInterval", source)
        self.assertIn("/api/system/capabilities", source)


if __name__ == "__main__":
    unittest.main()
