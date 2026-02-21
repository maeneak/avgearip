"""Tests for AVGear coordinator behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.helpers.update_coordinator import UpdateFailed

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.avgear_matrix.api import (
    AVGearCommandError,
    AVGearConnectionError,
    AVGearMatrixClient,
    MatrixStatus,
)
from custom_components.avgear_matrix.const import (
    CONF_DEVICE_UID,
    CONF_HOST,
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    CONF_PORT,
    DOMAIN,
)
from custom_components.avgear_matrix.coordinator import AVGearMatrixCoordinator


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: "uid-test",
        },
    )


@pytest.mark.asyncio
async def test_update_data_raises_updatefailed_on_parse_error(hass) -> None:
    """Parser command errors should fail the coordinator refresh."""
    entry = _entry()
    entry.add_to_hass(hass)

    client = AsyncMock(spec=AVGearMatrixClient)
    client.get_status.side_effect = AVGearCommandError("bad status")

    coordinator = AVGearMatrixCoordinator(hass, client, entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_tolerates_power_lock_query_failures(hass) -> None:
    """Supplementary power/lock query failures should not fail status update."""
    entry = _entry()
    entry.add_to_hass(hass)

    status = MatrixStatus(outputs={out: out for out in range(1, 9)})
    client = AsyncMock(spec=AVGearMatrixClient)
    client.get_status.return_value = status
    client.get_power_state.side_effect = AVGearConnectionError("power failed")
    client.get_lock_status.side_effect = AVGearConnectionError("lock failed")

    coordinator = AVGearMatrixCoordinator(hass, client, entry)
    result = await coordinator._async_update_data()

    assert result is status
