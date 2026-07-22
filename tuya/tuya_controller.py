import logging
from tuya_iot import TuyaOpenAPI, AuthType, TUYA_LOGGER

from config import TuyaConfig


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

    def get_status(self, device_id=None):
        """
        Obtiene el estado actual del dispositivo (incluyendo si está encendido o apagado).

        Returns:
            Un diccionario con el es1010tado del dispositivo o un error.
        """
        target_device_id = device_id or self.config.device_id
        if not target_device_id:
            return {"ok": False, "error": "device_id de Tuya no configurado"}

        try:
            response = self.api.get(f"/v1.0/devices/{target_device_id}/status")
            if response.get("success"):
                # Buscamos el código 'switch_1' que normalmente representa el estado on/off
                status = {item['code']: item['value'] for item in response['result']}
                return {"ok": True, "status": status}
            else:
                return {"ok": False, "error": response.get("msg", "Error desconocido")}
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
                return {"ok": True, "result": response.get("result")}
            else:
                return {"ok": False, "error": response.get("msg", "Error desconocido")}
        except Exception as e:
            return {"ok": False, "error": str(e)}
