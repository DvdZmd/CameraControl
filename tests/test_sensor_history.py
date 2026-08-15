import unittest
from datetime import datetime
from types import SimpleNamespace

from flask import Flask

from database.models import SensorReading, TimelapseFolder, db
from logs.sensor_logger import (
    SensorLoggingRuntime,
    persist_current_telemetry,
    reading_from_ble_state,
)
from routes.sensor_routes import sensor_bp


class SensorHistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(sensor_bp)
        with self.app.app_context():
            db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_ble_state_maps_the_four_environmental_values(self):
        reading = reading_from_ble_state({
            "DT": "21.5", "DH": "83.2", "DS": "18.4", "SP": "67",
            "P": "1500", "T": "1600",
        })

        self.assertEqual(reading.temperature_air, 21.5)
        self.assertEqual(reading.humidity_air, 83.2)
        self.assertEqual(reading.temperature_soil, 18.4)
        self.assertEqual(reading.humidity_soil, 67.0)
        self.assertIsNone(reading.pan_pulse_us)
        self.assertIsNone(reading.tilt_pulse_us)

    def test_incomplete_or_non_finite_state_is_rejected(self):
        self.assertIsNone(reading_from_ble_state({"DT": "20"}))
        self.assertIsNone(reading_from_ble_state({
            "DT": "nan", "DH": "70", "DS": "18", "SP": "50",
        }))

    def test_persist_current_telemetry_requires_connection(self):
        controller = SimpleNamespace(
            client=SimpleNamespace(is_connected=False),
            last_state={"DT": "20", "DH": "70", "DS": "18", "SP": "50"},
        )
        self.assertFalse(persist_current_telemetry(self.app, controller))
        with self.app.app_context():
            self.assertEqual(SensorReading.query.count(), 0)

    def test_persist_current_telemetry_saves_complete_sample(self):
        controller = SimpleNamespace(
            client=SimpleNamespace(is_connected=True),
            last_state={"DT": "20", "DH": "70", "DS": "18", "SP": "50"},
        )
        self.assertTrue(persist_current_telemetry(self.app, controller))
        with self.app.app_context():
            self.assertEqual(SensorReading.query.count(), 1)

    def test_history_filters_and_includes_entire_end_date(self):
        with self.app.app_context():
            folder = TimelapseFolder(folder_name="cultivo-agosto")
            db.session.add(folder)
            db.session.flush()
            db.session.add_all([
                SensorReading(
                    timestamp=datetime(2026, 8, 5, 23, 59),
                    temperature_air=20,
                    humidity_air=70,
                    temperature_soil=18,
                    humidity_soil=50,
                ),
                SensorReading(
                    timestamp=datetime(2026, 8, 6, 18, 30),
                    temperature_air=24,
                    humidity_air=80,
                    temperature_soil=19,
                    humidity_soil=60,
                    pan_pulse_us=1500,
                    tilt_pulse_us=1600,
                    timelapse_folder_id=folder.id,
                ),
            ])
            db.session.commit()

        response = self.client.get(
            "/api/sensors/readings?start_date=2026-08-06&end_date=2026-08-06"
            "&min_humidity_air=75"
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["readings"][0]["pan_pulse_us"], 1500)
        self.assertEqual(payload["readings"][0]["timelapse_folder_name"], "cultivo-agosto")
        self.assertEqual(payload["readings"][0]["timestamp"], "2026-08-06T18:30:00Z")

    def test_history_rejects_invalid_ranges(self):
        response = self.client.get(
            "/api/sensors/readings?min_temperature_air=30&max_temperature_air=20"
        )
        self.assertEqual(response.status_code, 400)

    def test_deletes_selected_and_all_sensor_readings(self):
        with self.app.app_context():
            db.session.add_all([
                SensorReading(
                    temperature_air=20,
                    humidity_air=70,
                    temperature_soil=18,
                    humidity_soil=50,
                ),
                SensorReading(
                    temperature_air=21,
                    humidity_air=71,
                    temperature_soil=19,
                    humidity_soil=51,
                ),
            ])
            db.session.commit()
            ids = [reading.id for reading in SensorReading.query.order_by(SensorReading.id)]

        response = self.client.delete("/api/sensors/readings", json={"ids": [ids[0]]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["deleted"], 1)

        response = self.client.delete("/api/sensors/readings/all", json={"confirm": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["deleted"], 1)
        with self.app.app_context():
            self.assertEqual(SensorReading.query.count(), 0)

    def test_delete_all_sensor_readings_requires_confirmation(self):
        response = self.client.delete("/api/sensors/readings/all", json={})
        self.assertEqual(response.status_code, 400)

    def test_logging_configuration_is_persisted_and_exposed(self):
        defaults = SimpleNamespace(enabled=True, interval_seconds=60)
        controller = SimpleNamespace(client=None, last_state={})
        runtime = SensorLoggingRuntime(self.app, controller, defaults)
        runtime.start()
        self.app.config["SENSOR_LOGGING_RUNTIME"] = runtime
        try:
            response = self.client.put("/api/sensors/logging-config", json={
                "enabled": False,
                "interval_seconds": 120,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {
                "enabled": False,
                "interval_seconds": 120.0,
            })

            restored = SensorLoggingRuntime(
                self.app,
                controller,
                SimpleNamespace(enabled=True, interval_seconds=10),
            )
            self.assertEqual(restored.status(), {
                "enabled": False,
                "interval_seconds": 120.0,
            })
        finally:
            runtime.stop_event.set()
            runtime.wake_event.set()
            runtime.thread.join(timeout=1)

    def test_logging_configuration_validates_interval(self):
        runtime = SimpleNamespace(
            status=lambda: {"enabled": True, "interval_seconds": 60.0},
            configure=lambda **values: values,
        )
        self.app.config["SENSOR_LOGGING_RUNTIME"] = runtime
        response = self.client.put("/api/sensors/logging-config", json={
            "enabled": True,
            "interval_seconds": 0,
        })
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
