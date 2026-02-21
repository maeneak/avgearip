"""Tests for AVGear API parser behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.avgear_matrix.api import AVGearCommandError, AVGearMatrixClient


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
