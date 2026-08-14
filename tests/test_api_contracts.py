import unittest
import json
import re
from pathlib import Path

from flask import Flask

from api_contract import OPENAPI_DOCUMENT, build_openapi_document
from profiles import resolve_profile
from routes.admin_routes import admin_bp
from routes.camera_routes import camera_bp
from routes.esp32_routes import esp32_bp, lighting_bp, pan_tilt_bp
from routes.sensor_routes import sensor_bp
from routes.system_routes import system_bp
from routes.timelapse_routes import timelapse_bp
from routes.tuya_routes import tuya_bp


ALL_BLUEPRINTS = (
    admin_bp,
    system_bp,
    camera_bp,
    esp32_bp,
    pan_tilt_bp,
    lighting_bp,
    sensor_bp,
    timelapse_bp,
    tuya_bp,
)


# Snapshot intencional del contrato HTTP existente. Un cambio en esta tabla debe
# tratarse como un cambio de API y revisarse junto con sus consumidores.
EXPECTED_API_RULES = {
    ("admin.trigger_reboot", "/api/admin/reboot", ("POST",)),
    ("admin.system_status", "/api/admin/system-status", ("GET",)),
    ("admin.trigger_update", "/api/admin/update", ("POST",)),
    ("camera_controller.index", "/api/camera/", ("GET",)),
    ("camera_controller.apply_preset", "/api/camera/apply_preset", ("POST",)),
    ("camera_controller.camera_status", "/api/camera/camera_status", ("GET",)),
    ("camera_controller.reset_camera", "/api/camera/reset", ("POST",)),
    ("camera_controller.start_stream", "/api/camera/stream/start", ("POST",)),
    ("camera_controller.stop_stream", "/api/camera/stream/stop", ("POST",)),
    ("camera_controller.take_photo_custom", "/api/camera/take_photo_custom", ("GET",)),
    ("camera_controller.update_settings", "/api/camera/update_settings", ("POST",)),
    ("camera_controller.video_feed", "/api/camera/video_feed", ("GET",)),
    ("camera_controller.video_feed_sync", "/api/camera/video_feed_sync", ("GET",)),
    ("camera.esp32_command", "/api/esp32/command", ("POST",)),
    ("camera.esp32_connect", "/api/esp32/connect", ("POST",)),
    ("camera.esp32_disconnect", "/api/esp32/disconnect", ("POST",)),
    ("camera.esp32_status", "/api/esp32/status", ("GET",)),
    ("lighting.esp32_light", "/api/esp32/light", ("POST",)),
    ("pan_tilt.esp32_center", "/api/esp32/center", ("POST",)),
    ("pan_tilt.esp32_move", "/api/esp32/move", ("POST",)),
    ("pan_tilt.esp32_return_to_saved_position", "/api/esp32/position/return", ("POST",)),
    ("pan_tilt.esp32_save_current_position", "/api/esp32/position/current", ("POST",)),
    ("pan_tilt.esp32_speed", "/api/esp32/speed", ("POST",)),
    ("sensors.sensor_logging_config", "/api/sensors/logging-config", ("GET", "PUT")),
    ("sensors.delete_sensor_readings", "/api/sensors/readings", ("DELETE",)),
    ("sensors.readings_history", "/api/sensors/readings", ("GET",)),
    ("sensors.delete_all_sensor_readings", "/api/sensors/readings/all", ("DELETE",)),
    ("system.capabilities", "/api/system/capabilities", ("GET",)),
    ("timelapse.download_timelapse_capture", "/api/timelapse/capture/download", ("GET",)),
    ("timelapse.delete_timelapse_captures", "/api/timelapse/captures", ("DELETE",)),
    ("timelapse.timelapse_captures", "/api/timelapse/captures", ("GET",)),
    ("timelapse.download_selected_captures", "/api/timelapse/captures/download", ("POST",)),
    ("timelapse.update_timelapse_config", "/api/timelapse/config", ("PUT",)),
    ("timelapse.timelapse_folders", "/api/timelapse/folders", ("GET",)),
    ("timelapse.delete_timelapse_folder", "/api/timelapse/folders/<folder_name>", ("DELETE",)),
    ("timelapse.download_timelapse_folder", "/api/timelapse/folders/<folder_name>/download", ("GET",)),
    ("timelapse.start_timelapse", "/api/timelapse/start", ("POST",)),
    ("timelapse.timelapse_status", "/api/timelapse/status", ("GET",)),
    ("timelapse.stop_timelapse", "/api/timelapse/stop", ("POST",)),
    ("tuya.list_tuya_devices", "/api/tuya/devices", ("GET",)),
    ("tuya.add_tuya_device", "/api/tuya/devices", ("POST",)),
    ("tuya.update_tuya_device", "/api/tuya/devices/<int:device_pk>", ("PATCH",)),
    ("tuya.refresh_tuya_device_details", "/api/tuya/devices/<int:device_pk>/details", ("POST",)),
    ("tuya.refresh_tuya_device_status", "/api/tuya/devices/<int:device_pk>/status", ("GET",)),
    ("tuya.set_tuya_device_status", "/api/tuya/devices/<int:device_pk>/status", ("POST",)),
    ("tuya.turn_off_plug", "/api/tuya/off", ("POST",)),
    ("tuya.turn_on_plug", "/api/tuya/on", ("POST",)),
    ("tuya.get_tuya_status", "/api/tuya/status", ("GET",)),
}


def _contract_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        PROJECT_PROFILE=resolve_profile("default"),
        INSTANCE_NAME="default",
        BLE_CAMERA_CONTROLLER=object(),
    )
    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)
    return app


class ApiSurfaceContractTests(unittest.TestCase):
    def test_complete_api_surface_matches_snapshot(self):
        app = _contract_app()

        actual = {
            (
                rule.endpoint,
                rule.rule,
                tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})),
            )
            for rule in app.url_map.iter_rules()
            if rule.rule.startswith("/api/")
        }

        self.assertEqual(actual, EXPECTED_API_RULES)

    def test_openapi_operations_match_complete_flask_surface(self):
        flask_operations = {
            (
                method.lower(),
                re.sub(r"<(?:int:)?([^>]+)>", r"{\1}", rule),
                endpoint,
            )
            for endpoint, rule, methods in EXPECTED_API_RULES
            for method in methods
        }
        documented_operations = {
            (method, path, operation["x-flask-endpoint"])
            for path, path_item in OPENAPI_DOCUMENT["paths"].items()
            for method, operation in path_item.items()
        }

        self.assertEqual(documented_operations, flask_operations)

    def test_checked_in_openapi_is_generated_from_contract_source(self):
        openapi_path = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
        checked_in = json.loads(openapi_path.read_text(encoding="utf-8"))

        self.assertEqual(checked_in, build_openapi_document())

    def test_openapi_local_references_resolve(self):
        schemas = OPENAPI_DOCUMENT["components"]["schemas"]

        def visit(value):
            if isinstance(value, dict):
                reference = value.get("$ref")
                if reference and reference.startswith("#/components/schemas/"):
                    self.assertIn(reference.rsplit("/", 1)[1], schemas)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(OPENAPI_DOCUMENT)

    def test_feature_extension_is_present_on_every_operation(self):
        valid_features = {
            "common", "camera", "esp32", "pan_tilt", "lighting",
            "sensors", "timelapse", "tuya",
        }
        for path_item in OPENAPI_DOCUMENT["paths"].values():
            for operation in path_item.values():
                self.assertIn(operation["x-cameracontrol-feature"], valid_features)

    def test_openapi_operation_ids_are_unique(self):
        operation_ids = [
            operation["operationId"]
            for path_item in OPENAPI_DOCUMENT["paths"].values()
            for operation in path_item.values()
        ]

        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_representative_validation_errors_keep_current_envelopes(self):
        client = _contract_app().test_client()
        cases = (
            ("post", "/api/admin/reboot", {}, 400, {"status", "message"}),
            ("post", "/api/camera/update_settings", [], 400, {"status", "message"}),
            ("post", "/api/esp32/command", [], 400, {"ok", "error"}),
            ("delete", "/api/sensors/readings", {}, 400, {"error"}),
            ("put", "/api/timelapse/config", [], 400, {"error"}),
            # La ruta comprueba disponibilidad de SQLite antes del payload.
            ("post", "/api/tuya/devices", [], 503, {"ok", "error"}),
        )

        for method, path, payload, status, keys in cases:
            with self.subTest(path=path):
                response = getattr(client, method)(path, json=payload)
                self.assertEqual(response.status_code, status)
                self.assertTrue(response.is_json)
                self.assertEqual(set(response.get_json()), keys)


if __name__ == "__main__":
    unittest.main()
