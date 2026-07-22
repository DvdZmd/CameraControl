import logging
import time
from tuya_iot import TuyaOpenAPI, AuthType, TUYA_LOGGER

from config import TuyaConfig


TUYA_STATUS_CACHE_TTL_SECONDS = 8

FAULT_BITS = (
    ("ov_cr", "Sobrecorriente"),
    ("ov_vol", "Sobretensión"),
    ("ov_pwr", "Sobrepotencia"),
    ("ls_cr", "Baja corriente"),
    ("ls_vol", "Subtensión"),
    ("ls_pow", "Baja potencia"),
)


def _scaled_number(value, scale):
    if not isinstance(value, (int, float)):
        return None
    return value / (10 ** scale)


def _decode_faults(value):
    if not isinstance(value, int):
        return []
    return [
        {"code": code, "label": label}
        for bit, (code, label) in enumerate(FAULT_BITS)
        if value & (1 << bit)
    ]


def normalize_tuya_status(status, switch_code="switch_1"):
    """
    Traduce los DPs reportados por Tuya a campos estables para el frontend.
    """
    if not isinstance(status, dict):
        status = {}

    voltage_v = _scaled_number(status.get("cur_voltage"), 1)
    power_w = _scaled_number(status.get("cur_power"), 1)
    energy_kwh = _scaled_number(status.get("add_ele"), 3)
    current_ma = status.get("cur_current")
    if not isinstance(current_ma, (int, float)):
        current_ma = None

    fault_raw = status.get("fault")
    return {
        "switch": {
            "code": switch_code,
            "is_on": status.get(switch_code) is True,
        },
        "electrical": {
            "voltage_v": voltage_v,
            "current_ma": current_ma,
            "power_w": power_w,
            "added_energy_kwh": energy_kwh,
        },
        "safety": {
            "fault_raw": fault_raw if isinstance(fault_raw, int) else None,
            "faults": _decode_faults(fault_raw),
            "child_lock": status.get("child_lock") if isinstance(status.get("child_lock"), bool) else None,
            "overcharge_switch": (
                status.get("overcharge_switch")
                if isinstance(status.get("overcharge_switch"), bool)
                else None
            ),
        },
        "settings": {
            "countdown_seconds": (
                status.get("countdown_1")
                if isinstance(status.get("countdown_1"), int)
                else None
            ),
            "relay_status": status.get("relay_status") if isinstance(status.get("relay_status"), str) else None,
            "light_mode": status.get("light_mode") if isinstance(status.get("light_mode"), str) else None,
            "cycle_time": status.get("cycle_time") if isinstance(status.get("cycle_time"), str) else None,
            "random_time": status.get("random_time") if isinstance(status.get("random_time"), str) else None,
            "switch_inching": status.get("switch_inching") if isinstance(status.get("switch_inching"), str) else None,
        },
        "capabilities": {
            "has_electrical_metering": any(
                code in status
                for code in ("cur_voltage", "cur_current", "cur_power", "add_ele")
            ),
            "has_fault_reporting": "fault" in status,
            "has_child_lock": "child_lock" in status,
            "has_countdown": "countdown_1" in status,
        },
    }


class TuyaController:
    """
    Controlador para interactuar con dispositivos Tuya a través de la API de Tuya IoT.
    """

    def __init__(self, config: TuyaConfig):
        """
        Inicializa el controlador de Tuya.

        Args:
            config: Objeto de configuración con las credenciales y el ID del dispositivo.
        """
        self.config = config
        self.api = TuyaOpenAPI(
            endpoint=config.api_endpoint,
            access_id=config.api_key,
            access_secret=config.api_secret,
            auth_type=AuthType.SMART_HOME
        )
        self.logger = logging.getLogger(__name__)
        self._status_cache = {}
        #self.api.connect(config.username, config.password, config.country_code, config.api_schema)
        # Desactivamos el logger de la librería Tuya para que no sea tan verboso
        TUYA_LOGGER.setLevel(logging.WARNING)

    def connect(self):
        """
        Conecta con la API de Tuya. Es necesario llamarlo antes de otras operaciones.
        """
        if not self.config.username or not self.config.password:
            return {
                "ok": False,
                "error": "Credenciales de Tuya no configuradas. Configure username y password en TuyaConfig.",
            }

        try:
            response = self.api.connect(
                username=self.config.username,
                password=self.config.password,
                country_code=self.config.country_code,
                schema=self.config.schema,
            )
            # Log full response for debugging permission issues
            self.logger.debug("Tuya connect response: %s", response)
            if not response.get("success"):
                return {
                    "ok": False,
                    "error": response.get("msg", "Error al conectar a Tuya."),
                    "details": response,
                }
            return {"ok": True, "message": "Conectado a la API de Tuya."}
        except Exception as e:
            self.logger.exception("Excepción al conectar con Tuya")
            return {"ok": False, "error": f"Error al conectar con la API de Tuya: {e}"}

    def get_status(self, device_id=None, switch_code="switch_1", force_refresh=False):
        """
        Obtiene el estado actual del dispositivo (incluyendo si está encendido o apagado).

        Returns:
            Un diccionario con el es1010tado del dispositivo o un error.
        """
        target_device_id = device_id or self.config.device_id
        if not target_device_id:
            return {"ok": False, "error": "device_id de Tuya no configurado"}

        cache_key = (target_device_id, switch_code)
        cached = self._status_cache.get(cache_key)
        now = time.monotonic()
        if (
            not force_refresh
            and cached is not None
            and now - cached["fetched_at_monotonic"] < TUYA_STATUS_CACHE_TTL_SECONDS
        ):
            return {**cached["result"], "cached": True}

        try:
            response = self.api.get(f"/v1.0/devices/{target_device_id}/status")
            if response.get("success"):
                status = {item['code']: item['value'] for item in response['result']}
                result = {
                    "ok": True,
                    "status": status,
                    "cached": False,
                    "fetched_at": int(time.time()),
                    **normalize_tuya_status(status, switch_code),
                }
                self._status_cache[cache_key] = {
                    "fetched_at_monotonic": now,
                    "result": result,
                }
                return result
            else:
                return {"ok": False, "error": response.get("msg", "Error desconocido")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_device_details(self, device_id=None):
        """
        Obtiene metadatos del dispositivo Tuya, incluyendo nombre remoto cuando
        la cuenta y el plan de API lo permiten.
        """
        target_device_id = device_id or self.config.device_id
        if not target_device_id:
            return {"ok": False, "error": "device_id de Tuya no configurado"}

        try:
            response = self.api.get(f"/v1.0/devices/{target_device_id}")
            if not response.get("success"):
                return {"ok": False, "error": response.get("msg", "Error desconocido")}

            result = response.get("result") or {}
            return {
                "ok": True,
                "device_id": target_device_id,
                "name": result.get("name") or result.get("device_name"),
                "online": result.get("online"),
                "product_name": result.get("product_name"),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_status(self, switch_state: bool, device_id=None, switch_code="switch_1"):
        """
        Enciende o apaga el enchufe.

        Args:
            switch_state: True para encender, False para apagar.

        Returns:
            Un diccionario confirmando el resultado de la operación.
        """
        target_device_id = device_id or self.config.device_id
        if not target_device_id:
            return {"ok": False, "error": "device_id de Tuya no configurado"}

        commands = {'commands': [{'code': switch_code, 'value': switch_state}]}
        try:
            response = self.api.post(f"/v1.0/devices/{target_device_id}/commands", commands)
            if response.get("success"):
                self._status_cache.pop((target_device_id, switch_code), None)
                return {"ok": True, "result": response.get("result")}
            else:
                return {"ok": False, "error": response.get("msg", "Error desconocido")}
        except Exception as e:
            return {"ok": False, "error": str(e)}
