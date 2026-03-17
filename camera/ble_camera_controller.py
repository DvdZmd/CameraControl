# ble_camera_controller.py
import asyncio
from typing import Optional
from bleak import BleakClient, BleakScanner


class Esp32BleCameraController:
    DEVICE_NAME = "ESP32-CameraHead"
    CHAR_RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    CHAR_TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

    def __init__(self, device_name: str | None = None, address: str | None = None):
        self.device_name = device_name or self.DEVICE_NAME
        self.address = address
        self.client: Optional[BleakClient] = None
        self.lock = asyncio.Lock()
        self.last_state: Optional[str] = None

    async def _notification_handler(self, _, data: bytearray):
        try:
            self.last_state = data.decode("utf-8", errors="ignore")
        except Exception:
            self.last_state = None

    async def discover_address(self) -> str:
        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if self.address and d.address == self.address:
                return d.address
            if d.name == self.device_name:
                return d.address
        raise RuntimeError(f"No se encontró el ESP32 BLE con nombre '{self.device_name}'")

    async def connect(self) -> dict:
        async with self.lock:
            if self.client and self.client.is_connected:
                return {
                    "connected": True,
                    "address": self.client.address,
                    "device_name": self.device_name,
                }

            address = self.address or await self.discover_address()
            client = BleakClient(address)

            await client.connect()

            if not client.is_connected:
                raise RuntimeError("No se pudo establecer conexión BLE con el ESP32")

            # Intentar suscribirse a notificaciones de estado
            try:
                await client.start_notify(self.CHAR_TX_UUID, self._notification_handler)
            except Exception:
                # No rompemos la conexión si la notify falla
                pass

            self.client = client
            self.address = address

            return {
                "connected": True,
                "address": address,
                "device_name": self.device_name,
            }

    async def disconnect(self) -> dict:
        async with self.lock:
            if self.client:
                try:
                    if self.client.is_connected:
                        try:
                            await self.client.stop_notify(self.CHAR_TX_UUID)
                        except Exception:
                            pass
                        await self.client.disconnect()
                finally:
                    self.client = None

            return {"connected": False}

    async def ensure_connected(self):
        if self.client and self.client.is_connected:
            return
        await self.connect()

    async def send_command(self, command: str) -> dict:
        async with self.lock:
            await self.ensure_connected()

            if not self.client or not self.client.is_connected:
                raise RuntimeError("ESP32 no conectado")

            payload = command.encode("utf-8")
            # Bleak expone write_gatt_char(...) async
            await self.client.write_gatt_char(self.CHAR_RX_UUID, payload)

            return {
                "ok": True,
                "command": command,
                "connected": True,
                "address": self.address,
            }

    async def set_speed(self, mode: int) -> dict:
        if mode < 0 or mode > 4:
            raise ValueError("speed mode debe estar entre 0 y 4")
        return await self.send_command(f"SET_SPEED:{mode}")

    async def center(self) -> dict:
        return await self.send_command("CENTER")

    async def get_status(self) -> dict:
        connected = bool(self.client and self.client.is_connected)
        return {
            "connected": connected,
            "address": self.address,
            "device_name": self.device_name,
            "last_state": self.last_state,
        }
    
#ble_camera_controller = Esp32BleCameraController()