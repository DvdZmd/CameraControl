"""Machine-readable description of CameraControl API version 1.

This module has no Flask or hardware imports. It is intentionally safe to use
from documentation tooling and future frontend client generators.
"""

from __future__ import annotations

import json


API_OPERATIONS = (
    ("GET", "/api/system/capabilities", "system.capabilities", "common", None, "Capabilities"),
    ("GET", "/api/admin/system-status", "admin.system_status", "common", None, "SystemStatus"),
    ("POST", "/api/admin/update", "admin.trigger_update", "common", None, "StatusMessage"),
    ("POST", "/api/admin/reboot", "admin.trigger_reboot", "common", "ConfirmationRequest", "StatusMessage"),
    ("GET", "/api/camera/", "camera_controller.index", "camera", None, None),
    ("POST", "/api/camera/apply_preset", "camera_controller.apply_preset", "camera", "PresetRequest", "StatusMessage"),
    ("GET", "/api/camera/camera_status", "camera_controller.camera_status", "camera", None, "CameraStatus"),
    ("POST", "/api/camera/reset", "camera_controller.reset_camera", "camera", None, "StatusMessage"),
    ("POST", "/api/camera/stream/start", "camera_controller.start_stream", "camera", None, "StreamState"),
    ("POST", "/api/camera/stream/stop", "camera_controller.stop_stream", "camera", None, "StreamState"),
    ("GET", "/api/camera/take_photo_custom", "camera_controller.take_photo_custom", "camera", None, None),
    ("POST", "/api/camera/update_settings", "camera_controller.update_settings", "camera", "CameraSettingsRequest", "CameraUpdateResult"),
    ("GET", "/api/camera/video_feed", "camera_controller.video_feed", "camera", None, None),
    ("GET", "/api/camera/video_feed_sync", "camera_controller.video_feed_sync", "camera", None, None),
    ("GET", "/api/esp32/status", "camera.esp32_status", "esp32", None, "Esp32Status"),
    ("POST", "/api/esp32/connect", "camera.esp32_connect", "esp32", None, "OpenResult"),
    ("POST", "/api/esp32/disconnect", "camera.esp32_disconnect", "esp32", None, "OpenResult"),
    ("POST", "/api/esp32/command", "camera.esp32_command", "esp32", "Esp32CommandRequest", "OpenResult"),
    ("POST", "/api/esp32/center", "pan_tilt.esp32_center", "pan_tilt", None, "OpenResult"),
    ("POST", "/api/esp32/move", "pan_tilt.esp32_move", "pan_tilt", "MoveRequest", "OpenResult"),
    ("POST", "/api/esp32/position/current", "pan_tilt.esp32_save_current_position", "pan_tilt", None, "OpenResult"),
    ("POST", "/api/esp32/position/return", "pan_tilt.esp32_return_to_saved_position", "pan_tilt", None, "OpenResult"),
    ("POST", "/api/esp32/speed", "pan_tilt.esp32_speed", "pan_tilt", "SpeedRequest", "OpenResult"),
    ("POST", "/api/esp32/light", "lighting.esp32_light", "lighting", "LightRequest", "OpenResult"),
    ("GET", "/api/sensors/logging-config", "sensors.sensor_logging_config", "sensors", None, "SensorLoggingConfig"),
    ("PUT", "/api/sensors/logging-config", "sensors.sensor_logging_config", "sensors", "SensorLoggingConfigRequest", "SensorLoggingConfig"),
    ("GET", "/api/sensors/readings", "sensors.readings_history", "sensors", None, "SensorReadingsPage"),
    ("DELETE", "/api/sensors/readings", "sensors.delete_sensor_readings", "sensors", "IdSelectionRequest", "DeleteResult"),
    ("DELETE", "/api/sensors/readings/all", "sensors.delete_all_sensor_readings", "sensors", "ConfirmationRequest", "DeleteResult"),
    ("GET", "/api/timelapse/status", "timelapse.timelapse_status", "timelapse", None, "TimelapseStatus"),
    ("PUT", "/api/timelapse/config", "timelapse.update_timelapse_config", "timelapse", "TimelapseConfigRequest", "TimelapseStatus"),
    ("POST", "/api/timelapse/start", "timelapse.start_timelapse", "timelapse", None, "TimelapseStatus"),
    ("POST", "/api/timelapse/stop", "timelapse.stop_timelapse", "timelapse", None, "TimelapseStatus"),
    ("GET", "/api/timelapse/folders", "timelapse.timelapse_folders", "timelapse", None, "FolderList"),
    ("GET", "/api/timelapse/captures", "timelapse.timelapse_captures", "timelapse", None, "CaptureList"),
    ("GET", "/api/timelapse/folders/{folder_name}/download", "timelapse.download_timelapse_folder", "timelapse", None, None),
    ("GET", "/api/timelapse/capture/download", "timelapse.download_timelapse_capture", "timelapse", None, None),
    ("GET", "/api/timelapse/capture/preview", "timelapse.preview_timelapse_capture", "timelapse", None, None),
    ("POST", "/api/timelapse/captures/download", "timelapse.download_selected_captures", "timelapse", "CaptureSelectionRequest", None),
    ("DELETE", "/api/timelapse/captures", "timelapse.delete_timelapse_captures", "timelapse", "CaptureSelectionRequest", "DeleteResult"),
    ("DELETE", "/api/timelapse/folders/{folder_name}", "timelapse.delete_timelapse_folder", "timelapse", None, "DeleteResult"),
    ("GET", "/api/tuya/status", "tuya.get_tuya_status", "tuya", None, "OpenResult"),
    ("POST", "/api/tuya/on", "tuya.turn_on_plug", "tuya", None, "OpenResult"),
    ("POST", "/api/tuya/off", "tuya.turn_off_plug", "tuya", None, "OpenResult"),
    ("GET", "/api/tuya/devices", "tuya.list_tuya_devices", "tuya", None, "TuyaDeviceList"),
    ("POST", "/api/tuya/devices", "tuya.add_tuya_device", "tuya", "TuyaDeviceCreateRequest", "TuyaDeviceResult"),
    ("PATCH", "/api/tuya/devices/{device_pk}", "tuya.update_tuya_device", "tuya", "TuyaDeviceUpdateRequest", "TuyaDeviceResult"),
    ("POST", "/api/tuya/devices/{device_pk}/details", "tuya.refresh_tuya_device_details", "tuya", None, "TuyaDeviceResult"),
    ("POST", "/api/tuya/devices/{device_pk}/status", "tuya.set_tuya_device_status", "tuya", "TuyaStatusRequest", "OpenResult"),
    ("GET", "/api/tuya/devices/{device_pk}/status", "tuya.refresh_tuya_device_status", "tuya", None, "TuyaDeviceResult"),
)


def _object(properties=None, *, required=(), additional=False, **keywords):
    schema = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": additional,
    }
    if required:
        schema["required"] = list(required)
    schema.update(keywords)
    return schema


SCHEMAS = {
    "Error": _object({"error": {"type": "string"}}, required=("error",)),
    "OkError": _object(
        {"ok": {"const": False}, "error": {"type": "string"}},
        required=("ok", "error"),
    ),
    "StatusMessage": _object(
        {"status": {"type": "string"}, "message": {"type": "string"}},
        required=("status",),
        additional=True,
    ),
    # Algunos resultados provienen directamente de controladores externos. Se
    # estabilizan sus discriminantes, manteniendo extensiones abiertas.
    "OpenResult": _object(
        {"ok": {"type": "boolean"}, "error": {"type": "string"}},
        additional=True,
    ),
    "Features": _object(
        {
            name: {"type": "boolean"}
            for name in (
                "camera", "timelapse", "esp32", "pan_tilt",
                "lighting", "sensors", "tuya",
            )
        },
        required=(
            "camera", "timelapse", "esp32", "pan_tilt",
            "lighting", "sensors", "tuya",
        ),
        additional={"type": "boolean"},
    ),
    "Capabilities": _object(
        {
            "api_version": {"type": "string", "const": "1"},
            "profile": {"type": "string"},
            "instance": {"type": "string"},
            "features": {"$ref": "#/components/schemas/Features"},
        },
        required=("api_version", "profile", "instance", "features"),
    ),
    "ConfirmationRequest": _object(
        {"confirm": {"type": "boolean", "const": True}},
        required=("confirm",),
    ),
    "SystemStatus": _object(
        {
            "cpu_temperature_c": {"type": ["number", "null"]},
            "cpu_usage_percent": {"type": ["number", "null"]},
            "power": {"type": ["object", "null"]},
            "storage": {"type": ["object", "null"]},
        },
        required=("cpu_temperature_c", "cpu_usage_percent", "power", "storage"),
    ),
    "PresetRequest": _object(
        {"preset": {"type": "string", "minLength": 1}}, required=("preset",)
    ),
    "StreamState": _object(
        {"status": {"type": "string"}, "stream_enabled": {"type": "boolean"}},
        required=("status", "stream_enabled"),
    ),
    "CameraSettingsRequest": _object(
        {
            "width": {"type": "integer", "minimum": 1, "maximum": 10000},
            "height": {"type": "integer", "minimum": 1, "maximum": 10000},
            "rotation": {"type": "integer", "enum": [0, 90, 180, 270]},
            "timelapse": {"type": "string", "enum": ["start", "stop"]},
            "interval": {"type": "integer", "minimum": 1},
            "t_width": {"type": "integer", "minimum": 1, "maximum": 10000},
            "t_height": {"type": "integer", "minimum": 1, "maximum": 10000},
            "Brightness": {"type": "number", "minimum": -1, "maximum": 1},
            "Contrast": {"type": "number", "minimum": 0, "maximum": 32},
            "Saturation": {"type": "number", "minimum": 0, "maximum": 32},
            "Sharpness": {"type": "number", "minimum": 0, "maximum": 16},
            "AfMode": {"type": "integer", "minimum": 0, "maximum": 2},
            "LensPosition": {"type": "number", "minimum": 0, "maximum": 32},
            "ExposureTime": {"type": "integer", "minimum": 1, "maximum": 1000000000},
            "AnalogueGain": {"type": "number", "minimum": 1, "maximum": 16},
            "AeEnable": {"type": "boolean"},
            "AwbMode": {},
            "DigitalGain": {},
        },
        minProperties=1,
    ),
    "CameraUpdateResult": _object(
        {
            "status": {"type": "string"},
            "current_rotation": {"type": "integer"},
            "pipeline_rotation": {"type": "integer"},
            "display_rotation": {"type": "integer"},
        },
        required=("status", "current_rotation", "pipeline_rotation", "display_rotation"),
    ),
    "CameraStatus": _object(
        {"available": {"type": "boolean"}, "stream_enabled": {"type": "boolean"}},
        additional=True,
    ),
    "Esp32CommandRequest": _object(
        {"command": {"type": "string"}}, required=("command",)
    ),
    "Esp32Status": _object(
        {
            "connected": {"type": "boolean"},
            "address": {"type": ["string", "null"]},
            "device_name": {"type": ["string", "null"]},
            "last_state": {"type": "object", "additionalProperties": True},
        },
        additional=True,
    ),
    "MoveRequest": _object(
        {"direction": {"type": "string", "enum": ["left", "right", "up", "down"]}},
        required=("direction",),
    ),
    "SpeedRequest": _object(
        {"mode": {"type": "integer", "minimum": 0, "maximum": 4}},
        required=("mode",),
    ),
    "LightRequest": {
        "oneOf": [
            _object({"on": {"type": "boolean"}}, required=("on",)),
            _object(
                {"intensity": {"type": "integer", "minimum": 0, "maximum": 100}},
                required=("intensity",),
            ),
        ]
    },
    "SensorLoggingConfigRequest": _object(
        {
            "enabled": {"type": "boolean"},
            "interval_seconds": {"type": "number", "minimum": 1, "maximum": 86400},
        },
        required=("enabled", "interval_seconds"),
    ),
    "SensorLoggingConfig": _object(
        {"enabled": {"type": "boolean"}, "interval_seconds": {"type": "number"}},
        additional=True,
    ),
    "IdSelectionRequest": _object(
        {
            "ids": {
                "type": "array", "minItems": 1, "maxItems": 5000,
                "items": {"type": "integer", "minimum": 1},
            }
        },
        required=("ids",),
    ),
    "DeleteResult": _object(
        {
            "ok": {"type": "boolean"}, "deleted": {"type": "integer"},
            "folder": {"type": "string"}, "deleted_folder": {"type": "string"},
        },
        required=("ok",),
        additional=True,
    ),
    "SensorReading": _object(
        {
            "id": {"type": "integer"}, "timestamp": {"type": "string", "format": "date-time"},
            "temperature_air": {"type": ["number", "null"]},
            "humidity_air": {"type": ["number", "null"]},
            "temperature_soil": {"type": ["number", "null"]},
            "humidity_soil": {"type": ["number", "null"]},
            "pan_pulse_us": {"type": ["integer", "null"]},
            "tilt_pulse_us": {"type": ["integer", "null"]},
            "timelapse_folder_id": {"type": ["integer", "null"]},
            "timelapse_folder_name": {"type": ["string", "null"]},
        },
        additional=True,
    ),
    "SensorReadingsPage": _object(
        {
            "page": {"type": "integer"}, "per_page": {"type": "integer"},
            "total": {"type": "integer"}, "pages": {"type": "integer"},
            "readings": {"type": "array", "items": {"$ref": "#/components/schemas/SensorReading"}},
        },
        required=("page", "per_page", "total", "pages", "readings"),
    ),
    "TimelapseConfigRequest": _object(
        {
            "interval_seconds": {"type": "integer", "minimum": 2},
            "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1},
            "auto_resume": {"type": "boolean"}, "light_enabled": {"type": "boolean"},
            "light_intensity": {"type": "integer", "minimum": 1, "maximum": 100},
            "light_warmup_seconds": {"type": "integer", "minimum": 0, "maximum": 60},
            "folder_name": {"type": "string"}, "save_sensor_readings": {"type": "boolean"},
        },
        required=("interval_seconds", "width", "height", "auto_resume"),
    ),
    "TimelapseStatus": _object(additional=True),
    "CaptureSelectionRequest": _object(
        {
            "folder": {"type": "string"},
            "captures": {"type": "array", "minItems": 1, "maxItems": 5000, "items": {"type": "string"}},
        },
        required=("folder", "captures"),
    ),
    "CaptureList": _object(
        {
            "folder": {"type": "string"},
            "page": {"type": "integer", "minimum": 1},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
            "captures": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "total": {"type": "integer"},
            "pages": {"type": "integer", "minimum": 0},
        },
        required=("folder", "page", "per_page", "captures", "total", "pages"),
    ),
    "FolderList": _object(
        {"folders": {"type": "array", "items": {}}, "selected": {"type": "string"}},
        required=("folders", "selected"),
    ),
    "TuyaDeviceCreateRequest": _object(
        {
            "name": {"type": "string", "minLength": 1, "maxLength": 120},
            "device_id": {"type": "string", "minLength": 1, "maxLength": 255},
            "switch_code": {"type": "string", "minLength": 1, "maxLength": 80, "default": "switch_1"},
        },
        required=("name", "device_id"),
    ),
    "TuyaDeviceUpdateRequest": _object(
        {"name": {"type": "string", "minLength": 1, "maxLength": 120}},
        required=("name",),
    ),
    "TuyaStatusRequest": _object(
        {"on": {"type": "boolean"}}, required=("on",)
    ),
    "TuyaDevice": _object(
        {
            "id": {"type": "integer"}, "name": {"type": "string"},
            "tuya_name": {"type": ["string", "null"]}, "device_id": {"type": "string"},
            "switch_code": {"type": "string"}, "enabled": {"type": "boolean"},
        },
        additional=True,
    ),
    "TuyaDeviceList": _object(
        {
            "ok": {"const": True},
            "devices": {"type": "array", "items": {"$ref": "#/components/schemas/TuyaDevice"}},
        },
        required=("ok", "devices"),
    ),
    "TuyaDeviceResult": _object(
        {
            "ok": {"type": "boolean"},
            "device": {"$ref": "#/components/schemas/TuyaDevice"},
            "error": {"type": "string"},
        },
    ),
}


def build_openapi_document():
    document = {
        "openapi": "3.1.0",
        "info": {
            "title": "CameraControl API",
            "version": "1.0.0",
            "description": "Contrato vigente para api_version 1.",
        },
        "servers": [{"url": "/"}],
        "paths": {},
        "components": {
            "schemas": SCHEMAS,
            "responses": {
                "Error": {
                    "description": "Error según el envelope histórico del módulo",
                    "content": {
                        "application/json": {
                            "schema": {
                                "oneOf": [
                                    {"$ref": "#/components/schemas/Error"},
                                    {"$ref": "#/components/schemas/OkError"},
                                    {"$ref": "#/components/schemas/StatusMessage"},
                                ]
                            }
                        }
                    },
                }
            },
        },
    }
    endpoint_counts = {}
    for operation in API_OPERATIONS:
        endpoint_counts[operation[2]] = endpoint_counts.get(operation[2], 0) + 1

    success_statuses = {
        "admin.trigger_reboot": "202",
        "tuya.add_tuya_device": "201",
    }
    for method, path, endpoint, feature, request_schema, response_schema in API_OPERATIONS:
        operation_id = (
            f"{endpoint}.{method.lower()}"
            if endpoint_counts[endpoint] > 1
            else endpoint
        )
        success_status = success_statuses.get(endpoint, "200")
        operation = {
            "operationId": operation_id,
            "tags": [feature],
            "x-cameracontrol-feature": feature,
            "x-flask-endpoint": endpoint,
            "responses": {
                success_status: {"description": "Respuesta correcta"},
                "default": {"$ref": "#/components/responses/Error"},
            },
        }
        if request_schema:
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{request_schema}"}
                    }
                },
            }
        if response_schema:
            operation["responses"][success_status]["content"] = {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{response_schema}"}
                }
            }
        parameters = []
        if "{folder_name}" in path:
            parameters.append({
                "name": "folder_name", "in": "path", "required": True,
                "schema": {"type": "string"},
            })
        if "{device_pk}" in path:
            parameters.append({
                "name": "device_pk", "in": "path", "required": True,
                "schema": {"type": "integer", "minimum": 1},
            })
        if parameters:
            operation["parameters"] = parameters
        document["paths"].setdefault(path, {})[method.lower()] = operation
    return document


OPENAPI_DOCUMENT = build_openapi_document()


if __name__ == "__main__":
    print(json.dumps(OPENAPI_DOCUMENT, indent=2, ensure_ascii=False))
