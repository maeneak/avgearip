"""Tests for AVGear API parser behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.avgear_matrix.api import (
    AVGearCommandError,
    AVGearMatrixClient,
    _clean_response,
)


def _full_status_response() -> str:
    return (
        "AV:01->01 AV:02->02 AV:03->03 AV:04->04 "
        "AV:05->05 AV:06->06 AV:07->07 AV:08->08"
    )


def test_parse_status_success_full_coverage() -> None:
    """Status parser should return a full output map."""
    client = AVGearMatrixClient("192.0.2.10")

    parsed = client._parse_status_response(_full_status_response())

    assert parsed == {out: out for out in range(1, 9)}


def test_parse_status_off_value() -> None:
    """Status parser should treat input 0 as output off."""
    client = AVGearMatrixClient("192.0.2.10")

    parsed = client._parse_status_response(
        "O1-I0 O2-I2 O3-I3 O4-I4 O5-I5 O6-I6 O7-I7 O8-I8"
    )

    assert parsed[1] is None
    assert parsed[2] == 2
    assert parsed[8] == 8


def test_parse_status_incomplete_raises() -> None:
    """Parser should reject incomplete status responses."""
    client = AVGearMatrixClient("192.0.2.10")

    with pytest.raises(AVGearCommandError, match="Incomplete status response"):
        client._parse_status_response("AV:01->01 AV:02->02")


def test_parse_status_unparseable_raises() -> None:
    """Parser should reject malformed responses."""
    client = AVGearMatrixClient("192.0.2.10")

    with pytest.raises(AVGearCommandError, match="Failed to parse status response"):
        client._parse_status_response("garbage")


@pytest.mark.asyncio
async def test_get_status_is_atomic_on_parse_error() -> None:
    """A parse failure should not overwrite the last known valid status map."""
    client = AVGearMatrixClient("192.0.2.10")
    client.status.outputs = {out: out for out in range(1, 9)}
    client._send_command = AsyncMock(return_value="AV:01->01")

    with pytest.raises(AVGearCommandError):
        await client.get_status()

    assert client.status.outputs == {out: out for out in range(1, 9)}


def test_clean_response_strips_null_bytes() -> None:
    """Null bytes embedded in connection-status responses should be removed."""
    raw = b"In   01 02 03 04\x00\r\nConnect  Y Y Y Y \r\n"
    assert _clean_response(raw) == b"In   01 02 03 04\r\nConnect  Y Y Y Y \r\n"


def test_clean_response_strips_session_banner() -> None:
    """The session banner prefix should be stripped from first-in-session responses."""
    raw = b"Please Input Your Command :\r\nCS4K-88 V2\r\n"
    assert _clean_response(raw) == b"CS4K-88 V2\r\n"


def test_clean_response_handles_banner_with_leading_whitespace() -> None:
    """Banner detection should tolerate leading whitespace."""
    raw = b"\r\nPlease Input Your Command :\r\nV1.0.2\r\n"
    assert _clean_response(raw) == b"V1.0.2\r\n"


def test_clean_response_leaves_normal_responses_untouched() -> None:
    """Responses without banner or nulls should pass through unchanged."""
    raw = b"AV:01->01 AV:02->02\r\n"
    assert _clean_response(raw) == raw


# --- Y/N table parser (HDCP, connection state) ---

_HDCP_ACTIVE_RESPONSE = (
    "In   01 02 03 04\r\nHDCP  N  N  N  Y\r\n"
    "In   05 06 07 08\r\nHDCP  N  N  N  N\r\n"
)
_HDCPEN_RESPONSE = (
    "In   01 02 03 04\r\nHDCPEN  N N N Y \r\n"
    "In   05 06 07 08\r\nHDCPEN  N N N N \r\n"
)
_OUTPUT_CONNECTION_RESPONSE = (
    "Out  01 02 03 04\r\nConnect  N Y Y Y \r\n"
    "Out  05 06 07 08\r\nConnect  Y Y Y N \r\n"
)


def test_parse_yn_table_input_hdcp_live_state() -> None:
    """%9973. should decode to the right per-port Y/N map."""
    parsed = AVGearMatrixClient._parse_yn_table(_HDCP_ACTIVE_RESPONSE, "HDCP", 8)
    assert parsed == {1: False, 2: False, 3: False, 4: True,
                      5: False, 6: False, 7: False, 8: False}


def test_parse_yn_table_hdcpen_setting() -> None:
    """%9978. (HDCPEN) should parse correctly despite the longer label."""
    parsed = AVGearMatrixClient._parse_yn_table(_HDCPEN_RESPONSE, "HDCPEN", 8)
    assert parsed[4] is True
    assert parsed[1] is False


def test_parse_yn_table_output_connection() -> None:
    """%9972. connection state should be parsed across both banks."""
    parsed = AVGearMatrixClient._parse_yn_table(_OUTPUT_CONNECTION_RESPONSE, "Connect", 8)
    assert parsed == {1: False, 2: True, 3: True, 4: True,
                      5: True, 6: True, 7: True, 8: False}


def test_parse_yn_table_garbage_returns_all_none() -> None:
    """Unparseable responses should not raise; map is all None."""
    parsed = AVGearMatrixClient._parse_yn_table("nonsense", "HDCP", 8)
    assert all(v is None for v in parsed.values())


def test_parse_resolution_table() -> None:
    """%9976. should give per-output string values."""
    response = (
        "Resolution\r\nOut 1 1920x1080p\r\nOut 2 3840x2160p\r\n"
        "Out 3 1920x1080p\r\nOut 4 1920x1080p\r\n"
        "Out 5 1920x1080p\r\nOut 6 1920x1080p\r\n"
        "Out 7 1920x1080p\r\nOut 8 1920x1080p\r\n"
    )
    parsed = AVGearMatrixClient._parse_resolution_table(response, 8)
    assert parsed[1] == "1920x1080p"
    assert parsed[2] == "3840x2160p"


# --- Setter validation ---

@pytest.mark.asyncio
async def test_set_input_edid_profile_rejects_bad_slot() -> None:
    """Profile out of 1-6 range must be rejected before a command is sent."""
    client = AVGearMatrixClient("192.0.2.10")
    client._send_command = AsyncMock(return_value="")
    with pytest.raises(AVGearCommandError):
        await client.set_input_edid_profile(1, 7)
    client._send_command.assert_not_called()


@pytest.mark.asyncio
async def test_set_input_edid_profile_formats_command() -> None:
    """Valid call must emit ``EDID/NN/S.`` with zero-padded input."""
    client = AVGearMatrixClient("192.0.2.10")
    client._send_command = AsyncMock(return_value="")
    await client.set_input_edid_profile(3, 6)
    client._send_command.assert_awaited_once_with("EDID/03/6.")


@pytest.mark.asyncio
async def test_set_input_hdcp_accepts_all_sentinel() -> None:
    """The ``"ALL"`` sentinel should map to the documented command shape."""
    client = AVGearMatrixClient("192.0.2.10")
    client._send_command = AsyncMock(return_value="")
    await client.set_input_hdcp("ALL", True)
    client._send_command.assert_awaited_once_with("/%I/ALL:1.")


@pytest.mark.asyncio
async def test_set_output_hdcp_numeric() -> None:
    """Integer target should emit a two-digit port number."""
    client = AVGearMatrixClient("192.0.2.10")
    client._send_command = AsyncMock(return_value="")
    await client.set_output_hdcp(5, False)
    client._send_command.assert_awaited_once_with("/%O/05:0.")


@pytest.mark.asyncio
async def test_copy_output_edid_rejects_out_of_range() -> None:
    """Copy command must validate both ports before issuing."""
    client = AVGearMatrixClient("192.0.2.10")
    client._send_command = AsyncMock(return_value="")
    with pytest.raises(AVGearCommandError):
        await client.copy_output_edid_to_input(99, 1)
    client._send_command.assert_not_called()
