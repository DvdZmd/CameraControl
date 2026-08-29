import asyncio
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Optional

from bleak import BleakClient, BleakScanner


class Esp32Controller:
    #TODO make this a singleton or manage multiple devices if needed in the future
    #TODO make these values configurable from a file or database
    DEVICE_NAME = "ESP32-FungiESP"
    CHAR_RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    CHAR_TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
    CONNECT_RETRIES = 3
    COMMAND_RETRIES = 2

    def __init__(self, device_name: str | None = None, address: str | None = None):
        """
        Initialize the BLE controller and start its dedicated event loop thread.

        The controller owns a private asyncio loop running in a background
        thread so synchronous Flask handlers can submit BLE tasks safely. BLE
        operations are expected to run on that loop; bypassing it may trigger
        event-loop affinity errors such as using a client attached to a
        different loop.

        Args:
            device_name: BLE advertised name to scan for when no address is
                pinned.
            address: Optional BLE MAC address or platform-specific identifier.

        Returns:
            None
        """
        self.device_name = device_name or self.DEVICE_NAME
        self.address = address
        self.client: Optional[BleakClient] = None
        self.last_state: dict = {}

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        """
        Run the private asyncio event loop forever.

        This method is intended to execute on the controller's background
        thread. All async BLE operations should be scheduled onto this loop.

        Returns:
            None
        """
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro, timeout: float = 10):
        """
        Execute a coroutine on the controller's event loop and wait for it.

        The coroutine is submitted to the dedicated BLE loop running on a
        background thread. This helper blocks the caller until completion or
        timeout, making it suitable for synchronous Flask endpoints.

        Args:
            coro: Coroutine object scheduled on the private event loop.
            timeout: Maximum wait time in seconds.

        Returns:
            The coroutine result.

        Raises:
            RuntimeError: If the coroutine does not finish before ``timeout``.
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            raise RuntimeError("Timeout ejecutando operación BLE")

    async def _notification_handler(self, _, data: bytearray):
        """
        Decode BLE notification payloads from the ESP32.

        This callback runs on the controller's private event loop when the BLE
        characteristic emits a notification. It updates in-memory state and does
        not perform additional synchronization.

        Args:
            _: Unused Bleak sender metadata.
            data: Raw BLE notification bytes.

        Returns:
            None
        """
        try:
            decoded_data = data.decode("utf-8", errors="ignore")
            # Parsea el formato "KEY1:VALUE1,KEY2:VALUE2,..."
            state_dict = {}
            for part in decoded_data.split(','):
                if ':' in part:
                    key, value = part.split(':', 1)
                    state_dict[key.strip()] = value.strip()
            self.last_state = state_dict
        except Exception:
            self.last_state = {"raw": data.hex()}

    async def _discover_address(self) -> str:
        """
        Scan for the target ESP32 BLE device and resolve its address.

        The scan interacts with the local BLE adapter and must run on the same
        event loop used by the rest of the controller's async BLE operations.

        Returns:
            The resolved BLE device address.

        Raises:
            RuntimeError: If no matching BLE device is discovered before the
                scan times out.
        """
        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if self.address and d.address == self.address:
                return d.address
            if d.name == self.device_name:
                return d.address
        raise RuntimeError(f"No se encontró el ESP32 BLE con nombre '{self.device_name}'")

    def _handle_disconnect(self, _client: BleakClient):
        """
        Clear the active client reference after a BLE disconnect callback.

        Args:
            _client: Disconnected Bleak client instance.

        Returns:
            None
        """
        self.client = None

    def set_target_sync(self, device_name: str, address: str | None = None) -> dict:
        """
        Configure the BLE target used by future connection attempts.

        The active BLE connection is not retargeted in place. Callers must
        disconnect before switching to a different advertised device.
        """
        requested_name = device_name.strip()
        requested_address = (
            address.strip()
            if isinstance(address, str)
            else (self.address if requested_name == self.device_name else None)
        )
        connected = bool(self.client and self.client.is_connected)
        target_changed = (
            requested_name != self.device_name
            or requested_address != self.address
        )
        if connected and target_changed:
            raise RuntimeError("Desconecte el ESP32 antes de cambiar el dispositivo BLE")

        self.device_name = requested_name
        self.address = requested_address
        return {
            "ok": True,
            "device_name": self.device_name,
            "address": self.address,
            "connected": connected,
        }

    async def _reset_client(self):
        """
        Stop notifications and disconnect the active BLE client.

        This method performs BLE teardown against the ESP32 when a client is
        connected. It is best-effort and intentionally suppresses disconnect
        errors during cleanup.

        Returns:
            None
        """
        if not self.client:
            return

        client = self.client
        self.client = None

        try:
            if client.is_connected:
                try:
                    await client.stop_notify(self.CHAR_TX_UUID)
                except Exception:
                    pass
                await client.disconnect()
        except Exception:
            pass

    async def _connect(self) -> dict:
        """
        Connect to the ESP32 over BLE and subscribe to notifications.

        The operation may scan for the device, open a BLE connection, and enable
        characteristic notifications. It retries on transient failures and must
        run on the controller's private event loop.

        Returns:
            A dictionary describing the BLE connection state and resolved
            address.

        Raises:
            RuntimeError: If the ESP32 cannot be discovered or connected after
                all retry attempts.
        """
        if self.client and self.client.is_connected:
            return {
                "connected": True,
                "address": self.client.address,
                "device_name": self.device_name,
            }

        last_error = None
        for attempt in range(self.CONNECT_RETRIES):
            try:
                await self._reset_client()
                address = self.address or await self._discover_address()
                client = BleakClient(address, disconnected_callback=self._handle_disconnect)
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
            except Exception as exc:
                last_error = exc
                await self._reset_client()
                if attempt + 1 < self.CONNECT_RETRIES:
                    await asyncio.sleep(0.5)

        raise RuntimeError(f"No se pudo conectar al ESP32: {last_error}") from last_error

    async def _disconnect(self) -> dict:
        """
        Disconnect from the ESP32 and release BLE resources.

        Returns:
            A dictionary reporting that the controller is disconnected.
        """
        await self._reset_client()

        return {"connected": False}

    async def _ensure_connected(self):
        """
        Ensure that a BLE connection to the ESP32 is available.

        Returns:
            None

        Raises:
            RuntimeError: If establishing the BLE connection fails.
        """
        if self.client and self.client.is_connected:
            return
        await self._connect()

    async def _send_command(self, command: str) -> dict:
        """
        Send a command to the ESP32 over BLE.

        The command is written to the configured RX GATT characteristic. The
        method retries once a connection is available and may reconnect if the
        transport fails. It must run on the controller's private event loop.

        Args:
            command: Command payload to send to the ESP32.

        Returns:
            A dictionary containing the command, connection state, and BLE
            address.

        Raises:
            RuntimeError: If the controller cannot connect or the command cannot
                be written after all retries.
        """
        last_error = None
        for attempt in range(self.COMMAND_RETRIES):
            try:
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
            except Exception as exc:
                last_error = exc
                await self._reset_client()
                if attempt + 1 < self.COMMAND_RETRIES:
                    await asyncio.sleep(0.2)

        raise RuntimeError(f"Error enviando comando '{command}': {last_error}") from last_error

    async def _center(self) -> dict:
        """
        Send the centering command to the ESP32.

        Returns:
            A dictionary describing the result of the BLE command.

        Raises:
            RuntimeError: If the centering command cannot be delivered.
        """
        return await self._send_command("CENTER")

    async def _set_speed(self, mode: int) -> dict:
        """
        Set the ESP32 movement speed preset.

        Args:
            mode: Speed preset identifier in the inclusive range 0 to 4.

        Returns:
            A dictionary describing the result of the BLE command.

        Raises:
            ValueError: If ``mode`` falls outside the accepted range.
            RuntimeError: If the BLE command cannot be delivered.
        """
        if mode < 0 or mode > 4:
            raise ValueError("speed mode debe estar entre 0 y 4")
        return await self._send_command(f"SET_SPEED:{mode}")

    async def _get_status(self) -> dict:
        """
        Report the cached BLE connection status.

        Returns:
            A dictionary containing connection state, resolved address, target
            device name, and the latest notification payload.
        """
        connected = bool(self.client and self.client.is_connected)
        return {
            "connected": connected,
            "address": self.address,
            "device_name": self.device_name,
            "last_state": self.last_state,
        }

    # Sync methods for Flask
    def connect_sync(self):
        """
        Connect to the ESP32 from synchronous code.

        This helper blocks the caller while the BLE connect coroutine runs on
        the controller's private event loop.

        Returns:
            A dictionary describing the BLE connection state.

        Raises:
            RuntimeError: If the BLE connection attempt fails or times out.
        """
        return self._run_coro(self._connect())

    def disconnect_sync(self):
        """
        Disconnect from the ESP32 from synchronous code.

        Returns:
            A dictionary reporting the disconnected state.

        Raises:
            RuntimeError: If the disconnect operation times out.
        """
        return self._run_coro(self._disconnect())

    def send_command_sync(self, command: str):
        """
        Send a BLE command to the ESP32 from synchronous code.

        Args:
            command: Command payload to send over BLE.

        Returns:
            A dictionary describing the command result.

        Raises:
            RuntimeError: If BLE transport fails or the operation times out.
        """
        return self._run_coro(self._send_command(command))

    def center_sync(self):
        """
        Center the ESP32-controlled mechanism from synchronous code.

        Returns:
            A dictionary describing the command result.

        Raises:
            RuntimeError: If BLE transport fails or the operation times out.
        """
        return self._run_coro(self._center())

    def set_speed_sync(self, mode: int):
        """
        Set the ESP32 speed preset from synchronous code.

        Args:
            mode: Speed preset identifier in the inclusive range 0 to 4.

        Returns:
            A dictionary describing the command result.

        Raises:
            ValueError: If ``mode`` falls outside the accepted range.
            RuntimeError: If BLE transport fails or the operation times out.
        """
        return self._run_coro(self._set_speed(mode))

    def get_status_sync(self):
        """
        Fetch cached BLE status from synchronous code.

        Returns:
            A dictionary with connection state and the latest received status.

        Raises:
            RuntimeError: If the status query times out.
        """
        return self._run_coro(self._get_status())
