import asyncio
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
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
        self.last_state: Optional[str] = None

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro, timeout: float = 10):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            raise RuntimeError("Timeout ejecutando operación BLE")

    async def _notification_handler(self, _, data: bytearray):
        try:
            self.last_state = data.decode("utf-8", errors="ignore")
        except Exception:
            self.last_state = None

    async def _discover_address(self) -> str:
        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if self.address and d.address == self.address:
                return d.address
            if d.name == self.device_name:
                return d.address
        raise RuntimeError(f"No se encontró el ESP32 BLE con nombre '{self.device_name}'")

    async def _connect(self) -> dict:
        if self.client and self.client.is_connected:
            return {
                "connected": True,
                "address": self.client.address,
                "device_name": self.device_name,
            }

        address = self.address or await self._discover_address()
        client = BleakClient(address)
        await client.connect()

        if not client.is_connected:
            raise RuntimeError("No se pudo establecer conexión BLE con el ESP32")

        try:
            await client.start_notify(self.CHAR_TX_UUID, self._notification_handler)
        except Exception:
            pass

        self.client = client
        self.address = address

        return {
            "connected": True,
            "address": address,
            "device_name": self.device_name,
        }

    async def _disconnect(self) -> dict:
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

    async def _ensure_connected(self):
        if self.client and self.client.is_connected:
            return
        await self._connect()

    async def _send_command(self, command: str) -> dict:
        await self._ensure_connected()

        if not self.client or not self.client.is_connected:
            raise RuntimeError("ESP32 no conectado")

        await self.client.write_gatt_char(self.CHAR_RX_UUID, command.encode("utf-8"))

        return {
            "ok": True,
            "command": command,
            "connected": True,
            "address": self.address,
        }

    async def _center(self) -> dict:
        return await self._send_command("CENTER")

    async def _set_speed(self, mode: int) -> dict:
        if mode < 0 or mode > 4:
            raise ValueError("speed mode debe estar entre 0 y 4")
        return await self._send_command(f"SET_SPEED:{mode}")

    async def _get_status(self) -> dict:
        connected = bool(self.client and self.client.is_connected)
        return {
            "connected": connected,
            "address": self.address,
            "device_name": self.device_name,
            "last_state": self.last_state,
        }

    # Métodos sync para Flask
    def connect_sync(self):
        return self._run_coro(self._connect())

    def disconnect_sync(self):
        return self._run_coro(self._disconnect())

    def send_command_sync(self, command: str):
        return self._run_coro(self._send_command(command))

    def center_sync(self):
        return self._run_coro(self._center())

    def set_speed_sync(self, mode: int):
        return self._run_coro(self._set_speed(mode))

    def get_status_sync(self):
        return self._run_coro(self._get_status())