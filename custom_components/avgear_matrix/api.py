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
BUFFER_SIZE = 4096  # Socket read buffer size
DRAIN_TIMEOUT = 0.1  # Timeout for draining additional response data

# The matrix emits this banner on the first response of a new TCP session.
_SESSION_BANNER = "Please Input Your Command :"


class AVGearConnectionError(Exception):
    """Exception for connection errors."""


class AVGearCommandError(Exception):
    """Exception for command errors."""


def _clean_response(data: bytes) -> bytes:
    """Strip embedded NUL bytes and the session banner prefix.

    The matrix firmware occasionally emits spurious ``\\x00`` bytes inside
    connection-status responses, and prefixes the first response of a new
    TCP session with ``Please Input Your Command :\\r\\n``.
    """
    cleaned = data.replace(b"\x00", b"")
    banner = _SESSION_BANNER.encode("ascii")
    if cleaned.lstrip().startswith(banner):
        cleaned = cleaned.lstrip()[len(banner):]
        # Drop the line-terminator that follows the banner, if any.
        cleaned = cleaned.lstrip(b"\r\n")
    return cleaned


@dataclass
class MatrixStatus:
    """Represents the current state of the matrix."""

    outputs: dict[int, int | None] = field(default_factory=dict)  # output -> input (None = off)
    model: str = ""
    firmware: str = ""
    locked: bool = False
    power_state: str = "PWON"  # PWON, PWOFF, STANDBY

    # HDCP — distinct meanings per row
    input_hdcp: dict[int, bool | None] = field(default_factory=dict)         # %9978. (HDCPEN setting)
    output_hdcp: dict[int, bool | None] = field(default_factory=dict)        # %9974. (display capability)
    input_hdcp_active: dict[int, bool | None] = field(default_factory=dict)  # %9973. (live negotiation)

    # Physical link state
    input_connected: dict[int, bool | None] = field(default_factory=dict)    # %9971.
    output_connected: dict[int, bool | None] = field(default_factory=dict)   # %9972.

    # Per-output resolution string as reported by %9976.
    output_resolution: dict[int, str | None] = field(default_factory=dict)

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
        self._port = int(port)
        self._num_inputs = int(num_inputs)
        self._num_outputs = int(num_outputs)
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
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("Error during disconnect: %s", exc)
            finally:
                self._writer = None
                self._reader = None
            _LOGGER.debug("Disconnected from AVGear Matrix")

    async def _send_command_raw(self, command: str) -> bytes:
        """Send a command and return the raw response bytes.

        Session banner prefix and embedded NUL bytes are stripped.
        Used for binary payloads such as EDID dumps.
        """
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
                    self._reader.read(BUFFER_SIZE),
                    timeout=DEFAULT_TIMEOUT,
                )
                chunks = [response]
                while True:
                    try:
                        more = await asyncio.wait_for(self._reader.read(BUFFER_SIZE), timeout=DRAIN_TIMEOUT)
                    except asyncio.TimeoutError:
                        break
                    if not more:
                        break
                    chunks.append(more)

                raw = _clean_response(b"".join(chunks))
                _LOGGER.debug("Received response: %d raw bytes", len(raw))
                return raw

            except asyncio.TimeoutError as err:
                await self.disconnect()
                raise AVGearConnectionError("Timeout waiting for response") from err
            except OSError as err:
                await self.disconnect()
                raise AVGearConnectionError(f"Communication error: {err}") from err

    async def _send_command(self, command: str) -> str:
        """Send a command and return the decoded ASCII response."""
        raw = await self._send_command_raw(command)
        response_text = raw.decode("ascii", errors="replace").strip()
        _LOGGER.debug("Received response: %s", response_text)
        return response_text

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
        parsed_outputs = self._parse_status_response(response)
        self._status.outputs = parsed_outputs
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
        """Route an input to an output.
        
        Note: Updates internal state optimistically as the AVGear protocol
        does not provide per-command success/failure responses. State will
        be synchronized on next status poll.
        """
        if not (1 <= input_num <= self._num_inputs) or not (1 <= output_num <= self._num_outputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs} and output 1-{self._num_outputs}")
        command = f"{input_num:02d}V{output_num:02d}."
        await self._send_command(command)
        self._status.outputs[output_num] = input_num
        return True

    async def route_input_to_all(self, input_num: int) -> bool:
        """Route an input to all outputs.
        
        Note: Updates internal state optimistically. See route_input_to_output.
        """
        if not (1 <= input_num <= self._num_inputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs}")
        command = f"{input_num:02d}All."
        await self._send_command(command)
        for out in range(1, self._num_outputs + 1):
            self._status.outputs[out] = input_num
        return True

    async def switch_off_output(self, output_num: int) -> bool:
        """Switch off (close) an output.
        
        Note: Updates internal state optimistically. See route_input_to_output.
        """
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
        """Switch off all outputs.
        
        Note: Updates internal state optimistically. See route_input_to_output.
        """
        await self._send_command("All$.")
        for out in range(1, self._num_outputs + 1):
            self._status.outputs[out] = None
        return True

    async def all_through(self) -> bool:
        """Route input 1->out1, 2->out2, etc.
        
        Note: Updates internal state optimistically. See route_input_to_output.
        """
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

    # --- HDCP Commands ---

    async def set_input_hdcp(self, input_num: int | str, compliant: bool) -> bool:
        """Set HDCP compliance for an input (or "ALL")."""
        self._validate_port_or_all(input_num, self._num_inputs, "Input")
        target = "ALL" if isinstance(input_num, str) else f"{input_num:02d}"
        flag = "1" if compliant else "0"
        await self._send_command(f"/%I/{target}:{flag}.")
        if isinstance(input_num, int):
            self._status.input_hdcp[input_num] = compliant
        else:
            for i in range(1, self._num_inputs + 1):
                self._status.input_hdcp[i] = compliant
        return True

    async def set_output_hdcp(self, output_num: int | str, compliant: bool) -> bool:
        """Set HDCP compliance for an output (or "ALL")."""
        self._validate_port_or_all(output_num, self._num_outputs, "Output")
        target = "ALL" if isinstance(output_num, str) else f"{output_num:02d}"
        flag = "1" if compliant else "0"
        await self._send_command(f"/%O/{target}:{flag}.")
        if isinstance(output_num, int):
            self._status.output_hdcp[output_num] = compliant
        else:
            for i in range(1, self._num_outputs + 1):
                self._status.output_hdcp[i] = compliant
        return True

    async def auto_hdcp(self) -> bool:
        """Run Auto HDCP management (%0801.)."""
        await self._send_command("%0801.")
        return True

    async def get_input_hdcp(self) -> dict[int, bool | None]:
        """Query input HDCP compliance setting (%9978. / HDCPEN)."""
        response = await self._send_command("%9978.")
        parsed = self._parse_yn_table(response, "HDCPEN", self._num_inputs)
        self._status.input_hdcp = parsed
        return parsed

    async def get_output_hdcp(self) -> dict[int, bool | None]:
        """Query downstream display HDCP capability (%9974.)."""
        response = await self._send_command("%9974.")
        parsed = self._parse_yn_table(response, "HDCP", self._num_outputs)
        self._status.output_hdcp = parsed
        return parsed

    async def get_input_hdcp_active(self) -> dict[int, bool | None]:
        """Query live HDCP negotiation state per input (%9973.)."""
        response = await self._send_command("%9973.")
        parsed = self._parse_yn_table(response, "HDCP", self._num_inputs)
        self._status.input_hdcp_active = parsed
        return parsed

    # --- Connection & Resolution Queries ---

    async def get_input_connection(self) -> dict[int, bool | None]:
        """Query input cable connection state (%9971.)."""
        response = await self._send_command("%9971.")
        parsed = self._parse_yn_table(response, "Connect", self._num_inputs)
        self._status.input_connected = parsed
        return parsed

    async def get_output_connection(self) -> dict[int, bool | None]:
        """Query output cable connection state (%9972.)."""
        response = await self._send_command("%9972.")
        parsed = self._parse_yn_table(response, "Connect", self._num_outputs)
        self._status.output_connected = parsed
        return parsed

    async def get_output_resolution(self) -> dict[int, str | None]:
        """Query per-output resolution (%9976.)."""
        response = await self._send_command("%9976.")
        parsed = self._parse_resolution_table(response, self._num_outputs)
        self._status.output_resolution = parsed
        return parsed

    # --- EDID Commands ---

    async def set_input_edid_profile(self, input_num: int, profile: int) -> bool:
        """Set input EDID to a built-in slot (1-6) via EDID/x/y."""
        if not (1 <= input_num <= self._num_inputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs}")
        if not (1 <= profile <= 6):
            raise AVGearCommandError("EDID profile must be 1-6")
        await self._send_command(f"EDID/{input_num:02d}/{profile}.")
        return True

    async def copy_output_edid_to_input(self, output_num: int, input_num: int) -> bool:
        """Copy a display's EDID onto an input (EDIDHxBy.)."""
        if not (1 <= input_num <= self._num_inputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs}")
        if not (1 <= output_num <= self._num_outputs):
            raise AVGearCommandError(f"Output must be 1-{self._num_outputs}")
        await self._send_command(f"EDIDH{output_num}B{input_num}.")
        return True

    async def force_input_edid_pcm(self, input_num: int) -> bool:
        """Force the audio section of an input's EDID to PCM (EDIDPCMx.)."""
        if not (1 <= input_num <= self._num_inputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs}")
        await self._send_command(f"EDIDPCM{input_num}.")
        return True

    async def reset_all_edid(self) -> bool:
        """Restore factory-default EDID on every input (EDIDMInit.)."""
        await self._send_command("EDIDMInit.")
        return True

    async def dump_input_edid(self, input_num: int) -> bytes:
        """Return the raw EDID bytes currently loaded on an input."""
        if not (1 <= input_num <= self._num_inputs):
            raise AVGearCommandError(f"Input must be 1-{self._num_inputs}")
        return await self._send_command_raw(f"GetInPortEDID{input_num}.")

    async def dump_output_edid(self, output_num: int) -> bytes:
        """Return the raw EDID bytes from the display on an output (EDIDGx.)."""
        if not (1 <= output_num <= self._num_outputs):
            raise AVGearCommandError(f"Output must be 1-{self._num_outputs}")
        return await self._send_command_raw(f"EDIDG{output_num}.")

    async def dump_builtin_edid(self, slot: int) -> bytes:
        """Return the raw bytes of a built-in EDID slot (GetIntEDIDx.)."""
        if not (1 <= slot <= 6):
            raise AVGearCommandError("EDID slot must be 1-6")
        return await self._send_command_raw(f"GetIntEDID{slot}.")

    # --- Parse Helpers ---

    def _validate_port_or_all(self, port: int | str, maximum: int, label: str) -> None:
        """Validate an int port in range, or the literal string 'ALL'."""
        if isinstance(port, str):
            if port.upper() != "ALL":
                raise AVGearCommandError(f"{label} must be an integer or 'ALL'")
            return
        if not (1 <= port <= maximum):
            raise AVGearCommandError(f"{label} must be 1-{maximum} or 'ALL'")

    def _parse_status_response(self, response: str) -> dict[int, int | None]:
        """Parse the Status. command response.
        
        Expected response formats:
        - "AV:01->01 IR:01->01 AV:02->02..." (AVGear format: AV:input->output)
        - "O1-I1 O2-I2 O3-I3..." (compact format)
        - "Output1:Input1 Output2:Input2..." (verbose format)
        - "1:2 3:4..." (simple number pairs)
        """
        parsed_outputs = {out: None for out in range(1, self._num_outputs + 1)}
        covered_outputs: set[int] = set()

        # Pattern: Try AVGear format first (AV:input->output), then fallback patterns
        patterns = [
            (r"AV:(\d+)->(\d+)", "input_output"),  # AV:01->02 means input 1 to output 2
            (r"O(\d+)[:\-]I(\d+)", "output_input"),  # O1-I2 or O1:I2
            (r"Out(?:put)?(\d+)[:\-]In(?:put)?(\d+)", "output_input"),  # Output1:Input2
            (r"(\d+)[:\-](\d+)", "output_input"),  # Simple 1:2 pairs (output:input)
        ]

        parse_success = False
        for pattern, order in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                valid_match_count = 0
                for first_str, second_str in matches:
                    try:
                        first_num = int(first_str)
                        second_num = int(second_str)

                        # Determine input and output based on pattern type
                        if order == "input_output":
                            in_num, out_num = first_num, second_num
                        else:  # output_input
                            out_num, in_num = first_num, second_num

                        if 1 <= out_num <= self._num_outputs and 0 <= in_num <= self._num_inputs:
                            valid_match_count += 1
                            parsed_outputs[out_num] = in_num if in_num > 0 else None
                            covered_outputs.add(out_num)
                    except ValueError:
                        continue

                if valid_match_count > 0:
                    parse_success = True
                    break

        if not parse_success:
            raise AVGearCommandError(f"Failed to parse status response: {response!r}")

        missing_outputs = set(range(1, self._num_outputs + 1)) - covered_outputs
        if missing_outputs:
            raise AVGearCommandError(
                f"Incomplete status response; missing outputs: {sorted(missing_outputs)}"
            )

        _LOGGER.debug("Parsed status: %s", parsed_outputs)
        return parsed_outputs

    def _parse_single_output(self, response: str, output: int) -> int | None:
        """Parse response for a single output query.
        
        Handles formats like:
        - "AV:01->02" (input 1 to output 2)
        - "Input 3" or "In3"
        - "closed" or "off" (output is off)
        """
        # Try AVGear format (AV:input->output) for the specific output
        av_match = re.search(rf"AV:(\d+)->{output:02d}", response)
        if av_match:
            input_num = int(av_match.group(1))
            if 1 <= input_num <= self._num_inputs:
                self._status.outputs[output] = input_num
                return input_num
        
        # Try to find an input number in generic format
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

    @staticmethod
    def _parse_yn_table(response: str, data_row_label: str, num_ports: int) -> dict[int, bool | None]:
        """Parse the ``In/Out  01 02 03 04\\n<LABEL>  Y N Y N`` table shape.

        The matrix returns four-column tables in two banks (ports 1-4 then 5-8,
        etc.). Header rows carry port numbers; data rows carry Y/N flags keyed
        by ``data_row_label`` (e.g. ``HDCP``, ``HDCPEN``, ``Connect``).
        """
        result: dict[int, bool | None] = {n: None for n in range(1, num_ports + 1)}

        header_pattern = re.compile(r"(?:In|Out)\s+((?:\d{1,2}\s*)+)", re.IGNORECASE)
        # Some firmware pads labels with trailing spaces; tolerate variable spacing.
        data_pattern = re.compile(
            rf"{re.escape(data_row_label)}\s+((?:[YN]\s*)+)", re.IGNORECASE
        )

        headers = header_pattern.findall(response)
        data_rows = data_pattern.findall(response)
        if not headers or not data_rows or len(headers) != len(data_rows):
            return result

        for header_chunk, data_chunk in zip(headers, data_rows):
            ports = [int(x) for x in header_chunk.split() if x.isdigit()]
            flags = [c for c in data_chunk.upper() if c in ("Y", "N")]
            for port, flag in zip(ports, flags):
                if 1 <= port <= num_ports:
                    result[port] = flag == "Y"

        return result

    @staticmethod
    def _parse_resolution_table(response: str, num_outputs: int) -> dict[int, str | None]:
        """Parse the ``Out N <resolution>`` rows from %9976. responses.

        Anchored to line-start so a multi-column header row like
        ``Out  01 02 03 04`` (returned by connection queries) can't be
        mis-parsed as a resolution row if the regex is ever pointed at the
        wrong response.
        """
        result: dict[int, str | None] = {n: None for n in range(1, num_outputs + 1)}
        for match in re.finditer(
            r"^\s*Out\s+(\d{1,2})\s+(\S+)\s*$", response, re.IGNORECASE | re.MULTILINE
        ):
            out_num = int(match.group(1))
            value = match.group(2).strip()
            if 1 <= out_num <= num_outputs and value:
                result[out_num] = value
        return result

    async def test_connection(self) -> dict[str, Any]:
        """Test connection and return device info."""
        await self.connect()
        info = {
            "model": await self.get_model(),
            "firmware": await self.get_firmware(),
        }
        return info
