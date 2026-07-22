import unittest

from flask import Flask

from database.models import TuyaDevice, db
from routes.tuya_routes import tuya_bp


class FakeTuyaController:
    def __init__(self):
        self.status_by_device = {}
        self.details_by_device = {}
        self.commands = []

    def get_status(self, device_id=None, switch_code="switch_1"):
        return {
            "ok": True,
            "status": self.status_by_device.get(device_id, {"switch_1": False}),
        }

    def set_status(self, switch_state, device_id=None, switch_code="switch_1"):
        self.commands.append((device_id, switch_code, switch_state))
        return {"ok": True, "result": True}

    def get_device_details(self, device_id=None):
        return {
            "ok": True,
            "name": self.details_by_device.get(device_id, f"Tuya {device_id}"),
        }


class TuyaRoutesTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.controller = FakeTuyaController()
        app.config["TUYA_CONTROLLER"] = self.controller
        db.init_app(app)
        app.register_blueprint(tuya_bp)
        self.app = app

        with app.app_context():
            db.create_all()

        self.client = app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_adds_tuya_device(self):
        self.controller.details_by_device["device-123"] = "Nombre en Tuya"

        response = self.client.post("/api/tuya/devices", json={
            "name": "Luz cultivo",
            "device_id": "device-123",
            "switch_code": "switch_1",
        })

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["device"]["name"], "Luz cultivo")
        self.assertEqual(payload["device"]["tuya_name"], "Nombre en Tuya")
        with self.app.app_context():
            saved = TuyaDevice.query.one()
            self.assertEqual(saved.device_id, "device-123")
            self.assertEqual(saved.tuya_name, "Nombre en Tuya")

    def test_rejects_duplicate_device_id(self):
        self.client.post("/api/tuya/devices", json={
            "name": "Luz cultivo",
            "device_id": "device-123",
        })

        response = self.client.post("/api/tuya/devices", json={
            "name": "Otra luz",
            "device_id": "device-123",
        })

        self.assertEqual(response.status_code, 409)

    def test_rejects_invalid_device_payload(self):
        response = self.client.post("/api/tuya/devices", json={
            "name": "",
            "device_id": "device-123",
        })

        self.assertEqual(response.status_code, 400)

    def test_lists_devices_with_status(self):
        with self.app.app_context():
            db.session.add(TuyaDevice(
                name="Bomba",
                device_id="pump-1",
                switch_code="switch_1",
            ))
            db.session.commit()
        self.controller.status_by_device["pump-1"] = {"switch_1": True}

        response = self.client.get("/api/tuya/devices")

        self.assertEqual(response.status_code, 200)
        devices = response.get_json()["devices"]
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["name"], "Bomba")
        self.assertTrue(devices[0]["is_on"])
        self.assertEqual(devices[0]["switch"]["code"], "switch_1")

    def test_lists_devices_with_normalized_electrical_data(self):
        with self.app.app_context():
            db.session.add(TuyaDevice(
                name="Luz cultivo",
                device_id="light-1",
                switch_code="switch_1",
            ))
            db.session.commit()
        self.controller.status_by_device["light-1"] = {
            "switch_1": True,
            "cur_voltage": 2284,
            "cur_current": 120,
            "cur_power": 253,
            "add_ele": 125,
            "fault": 5,
            "child_lock": False,
            "relay_status": "power_off",
            "light_mode": "relay",
            "countdown_1": 0,
        }

        response = self.client.get("/api/tuya/devices")

        self.assertEqual(response.status_code, 200)
        device = response.get_json()["devices"][0]
        self.assertEqual(device["electrical"]["voltage_v"], 228.4)
        self.assertEqual(device["electrical"]["current_ma"], 120)
        self.assertEqual(device["electrical"]["power_w"], 25.3)
        self.assertEqual(device["electrical"]["added_energy_kwh"], 0.125)
        self.assertTrue(device["capabilities"]["has_electrical_metering"])
        self.assertEqual(
            [fault["code"] for fault in device["safety"]["faults"]],
            ["ov_cr", "ov_pwr"],
        )
        self.assertEqual(device["settings"]["relay_status"], "power_off")

    def test_updates_local_device_name(self):
        with self.app.app_context():
            device = TuyaDevice(
                name="Alias viejo",
                tuya_name="Nombre Tuya",
                device_id="lamp-1",
                switch_code="switch_1",
            )
            db.session.add(device)
            db.session.commit()
            device_pk = device.id

        response = self.client.patch(
            f"/api/tuya/devices/{device_pk}",
            json={"name": "Alias nuevo"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["device"]
        self.assertEqual(payload["name"], "Alias nuevo")
        self.assertEqual(payload["tuya_name"], "Nombre Tuya")
        with self.app.app_context():
            saved = db.session.get(TuyaDevice, device_pk)
            self.assertEqual(saved.name, "Alias nuevo")

    def test_refreshes_remote_tuya_name(self):
        with self.app.app_context():
            device = TuyaDevice(
                name="Alias local",
                tuya_name=None,
                device_id="lamp-1",
                switch_code="switch_1",
            )
            db.session.add(device)
            db.session.commit()
            device_pk = device.id
        self.controller.details_by_device["lamp-1"] = "Nombre remoto"

        response = self.client.post(f"/api/tuya/devices/{device_pk}/details")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["device"]["tuya_name"], "Nombre remoto")
        with self.app.app_context():
            saved = db.session.get(TuyaDevice, device_pk)
            self.assertEqual(saved.tuya_name, "Nombre remoto")

    def test_sets_device_status_using_configured_device_id(self):
        with self.app.app_context():
            device = TuyaDevice(
                name="Humidificador",
                device_id="humidifier-1",
                switch_code="switch_led",
            )
            db.session.add(device)
            db.session.commit()
            device_pk = device.id

        response = self.client.post(
            f"/api/tuya/devices/{device_pk}/status",
            json={"on": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.controller.commands,
            [("humidifier-1", "switch_led", True)],
        )


if __name__ == "__main__":
    unittest.main()
