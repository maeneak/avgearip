"""AVGear Matrix TCP/IP API Client."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Connection settings
DEFAULT_TIMEOUT = 5.0
COMMAND_DELAY = 0.1  # Delay between commands


class AVGearConnectionError(Exception):
    """Exception for connection errors."""


class AVGearCommandError(Exception):
    """Exception for command errors."""


@dataclass
class MatrixStatus:
    """Represents the current state of the matrix."""

    outputs: dict[int, int | None] = field(default_factory=dict)  # output -> input (None = off)
    model: str = ""
    firmware: str = ""
    locked: bool = False
    power_state: str = "PWON"  # PWON, PWOFF, STANDBY

    def get_output_input(self, output: int) -> int | None:
        """Get the input routed to a specific output."""
        return self.outputs.get(output)


class AVGearMatrixClient:
    """Async TCP client for AVGear Matrix Switcher."""

    def __init__(
        self,
        host: str,
        port: int = 4001,
        num_inputs: int = 8,
        num_outputs: int = 8,
    ) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._num_inputs = num_inputs
        self._num_outputs = num_outputs
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._status = MatrixStatus()

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    @property
    def port(self) -> int:
        """Return the port."""
        return self._port

    @property
    def status(self) -> MatrixStatus:
        """Return the current status."""
        return self._status

    @property
    def connected(self) -> bool:
        """Return True if connected."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Establish TCP connection."""
        if self.connected:
            return

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=DEFAULT_TIMEOUT,
            )
            _LOGGER.debug("Connected to AVGear Matrix at %s:%s", self._host, self._port)
        except asyncio.TimeoutError as err:
            raise AVGearConnectionError(f"Timeout connecting to {self._host}:{self._port}") from err
        except OSError as err:
            raise AVGearConnectionError(f"Cannot connect to {self._host}:{self._port}: {err}") from err

    async def disconnect(self) -> None:
        """Close TCP connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._writer = None
                self._reader = None
            _LOGGER.debug("Disconnected from AVGear Matrix")

    async def _send_command(self, command: str) -> str:
        """Send a command and return the response."""
        async with self._lock:
            if not self.connected:
                await self.connect()

            if self._writer is None or self._reader is None:
                raise AVGearConnectionError("Not connected")

            try:
                _LOGGER.debug("Sending command: %s", command)
                self._writer.write(command.encode("ascii"))
                await self._writer.drain()

                # Small delay for device processing
                await asyncio.sleep(COMMAND_DELAY)

                # Read response with timeout; drain any additional data briefly
                response = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=DEFAULT_TIMEOUT,
                )
                chunks = [response]
                while True:
                    try:
                        more = await asyncio.wait_for(self._reader.read(4096), timeout=0.1)
                    except asyncio.TimeoutError:
                        break
                    if not more:
                        break
                    chunks.append(more)

                response_text = b"".join(chunks).decode("ascii", errors="replace").strip()
                _LOGGER.debug("Received response: %s", response_text)
                return response_text

            except asyncio.TimeoutError as err:
                await self.disconnect()
                raise AVGearConnectionError("Timeout waiting for response") from err
            except OSError as err:
                await self.disconnect()
                raise AVGearConnectionError(f"Communication error: {err}") from err

    # --- Query Commands ---

    async def get_model(self) -> str:
        """Query device model."""
        response = await self._send_command("/*Type;")
        self._status.model = response
        return response

    async def get_firmware(self) -> str:
        """Query firmware version."""
        response = await self._send_command("/^Version;")
        self._status.firmware = response
        return response

    async def get_status(self) -> MatrixStatus:
        """Query full routing status."""
        response = await self._send_command("Status.")
        self._parse_status_response(response)
        return self._status

    async def get_output_status(self, output: int) -> int | None:
        """Query status of a specific output."""
        response = await self._send_command(f"Status{output:02d}.")
        # Parse individual output response
        return self._parse_single_output(response, output)

    async def get_power_state(self) -> str:
        """Query power state."""
        response = await self._send_command("%9962.")
        if "STANDBY" in response.upper():
            self._status.power_state = "STANDBY"
        elif "PWOFF" in response.upper():
            self._status.power_state = "PWOFF"
        else:
            self._status.power_state = "PWON"
        return self._status.power_state

    async def get_lock_status(self) -> bool:
        """Query panel lock status."""
        response = await self._send_command("%9961.")
        self._status.locked = "locked" in response.lower()
        return self._status.locked

    # --- Switching Commands ---

    async def route_input_to_output(self, input_num: int, output_num: int) -> bool:
        """Route an input to an output."""
        if not (1 <= input_num <= self._num_inputs) or not (1 <= output_num <= self._num_outputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs} and output 1-{self._num_outputs}")
        command = f"{input_num:02d}V{output_num:02d}."
        await self._send_command(command)
        self._status.outputs[output_num] = input_num
        return True

    async def route_input_to_all(self, input_num: int) -> bool:
        """Route an input to all outputs."""
        if not (1 <= input_num <= self._num_inputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs}")
        command = f"{input_num:02d}All."
        await self._send_command(command)
        for out in range(1, self._num_outputs + 1):
            self._status.outputs[out] = input_num
        return True

    async def switch_off_output(self, output_num: int) -> bool:
        """Switch off (close) an output."""
        if not (1 <= output_num <= self._num_outputs):
            raise AVGearCommandError(f"Output must be 1-{self._num_outputs}")
        command = f"{output_num:02d}$."
        await self._send_command(command)
        self._status.outputs[output_num] = None
        return True

    async def switch_on_output(self, output_num: int) -> bool:
        """Switch on (open) an output."""
        if not (1 <= output_num <= self._num_outputs):
            raise AVGearCommandError(f"Output must be 1-{self._num_outputs}")
        command = f"{output_num:02d}@."
        await self._send_command(command)
        return True

    async def switch_off_all(self) -> bool:
        """Switch off all outputs."""
        await self._send_command("All$.")
        for out in range(1, self._num_outputs + 1):
            self._status.outputs[out] = None
        return True

    async def all_through(self) -> bool:
        """Route input 1->out1, 2->out2, etc."""
        await self._send_command("All#.")
        for i in range(1, self._num_outputs + 1):
            self._status.outputs[i] = i
        return True

    # --- Preset Commands ---

    async def save_preset(self, preset: int) -> bool:
        """Save current state to preset."""
        if not (0 <= preset <= 9):
            raise AVGearCommandError("Preset must be 0-9")
        await self._send_command(f"Save{preset}.")
        return True

    async def recall_preset(self, preset: int) -> bool:
        """Recall a preset."""
        if not (0 <= preset <= 9):
            raise AVGearCommandError("Preset must be 0-9")
        await self._send_command(f"Recall{preset}.")
        # Refresh status after preset recall
        await self.get_status()
        return True

    async def clear_preset(self, preset: int) -> bool:
        """Clear a preset."""
        if not (0 <= preset <= 9):
            raise AVGearCommandError("Preset must be 0-9")
        await self._send_command(f"Clear{preset}.")
        return True

    # --- Power Commands ---

    async def power_on(self) -> bool:
        """Set normal working mode."""
        await self._send_command("PWON.")
        self._status.power_state = "PWON"
        return True

    async def power_off(self) -> bool:
        """Set standby and cut power to receivers."""
        await self._send_command("PWOFF.")
        self._status.power_state = "PWOFF"
        return True

    async def standby(self) -> bool:
        """Set standby (keeps PoC power)."""
        await self._send_command("STANDBY.")
        self._status.power_state = "STANDBY"
        return True

    # --- Panel Lock Commands ---

    async def lock_panel(self) -> bool:
        """Lock front panel buttons."""
        await self._send_command("/%Lock;")
        self._status.locked = True
        return True

    async def unlock_panel(self) -> bool:
        """Unlock front panel buttons."""
        await self._send_command("/%Unlock;")
        self._status.locked = False
        return True

    # --- Parse Helpers ---

    def _parse_status_response(self, response: str) -> None:
        """Parse the Status. command response."""
        # Response format varies, but typically shows routing like:
        # "O1-I1 O2-I2 O3-I3..." or "Output1:Input1 Output2:Input2..."
        # We'll try to parse various formats

        # Initialize all outputs as None (unknown)
        for out in range(1, self._num_outputs + 1):
            if out not in self._status.outputs:
                self._status.outputs[out] = None

        # Pattern: O1-I2 or O01-I02 or Out1:In2
        patterns = [
            r"O(\d+)[:\-]I(\d+)",  # O1-I2 or O1:I2
            r"Out(?:put)?(\d+)[:\-]In(?:put)?(\d+)",  # Output1:Input2
            r"(\d+)[:\-](\d+)",  # Simple 1:2 pairs
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                for out_str, in_str in matches:
                    try:
                        out_num = int(out_str)
                        in_num = int(in_str)
                        if 1 <= out_num <= self._num_outputs and 0 <= in_num <= self._num_inputs:
                            self._status.outputs[out_num] = in_num if in_num > 0 else None
                    except ValueError:
                        continue
                break

        _LOGGER.debug("Parsed status: %s", self._status.outputs)

    def _parse_single_output(self, response: str, output: int) -> int | None:
        """Parse response for a single output query."""
        # Try to find an input number in the response
        match = re.search(r"[Ii]n(?:put)?[:\s]*(\d+)", response)
        if match:
            input_num = int(match.group(1))
            if 1 <= input_num <= self._num_inputs:
                self._status.outputs[output] = input_num
                return input_num

        # Check for "closed" or "off" indicators
        if "closed" in response.lower() or "off" in response.lower():
            self._status.outputs[output] = None
            return None

        return self._status.outputs.get(output)

    async def test_connection(self) -> dict[str, Any]:
        """Test connection and return device info."""
        await self.connect()
        info = {
            "model": await self.get_model(),
            "firmware": await self.get_firmware(),
        }
        return info
