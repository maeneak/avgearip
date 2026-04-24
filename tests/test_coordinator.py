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


@pytest.mark.asyncio
async def test_update_data_tolerates_diagnostic_query_failures(hass) -> None:
    """HDCP/connection/resolution failures must not break the refresh."""
    entry = _entry()
    entry.add_to_hass(hass)

    status = MatrixStatus(outputs={out: out for out in range(1, 9)})
    client = AsyncMock(spec=AVGearMatrixClient)
    client.get_status.return_value = status
    for attr in (
        "get_input_hdcp",
        "get_output_hdcp",
        "get_input_hdcp_active",
        "get_input_connection",
        "get_output_connection",
        "get_output_resolution",
    ):
        getattr(client, attr).side_effect = AVGearConnectionError(f"{attr} failed")

    coordinator = AVGearMatrixCoordinator(hass, client, entry)
    result = await coordinator._async_update_data()

    assert result is status


def _coordinator_with_stubbed_refresh(hass) -> tuple[AVGearMatrixCoordinator, AsyncMock]:
    """Build a coordinator whose async_request_refresh is a no-op.

    The EDID wrappers trigger a refresh after mutating state; in unit tests we
    don't want that cascade into the debouncer/update cycle.
    """
    entry = _entry()
    entry.add_to_hass(hass)
    client = AsyncMock(spec=AVGearMatrixClient)
    coordinator = AVGearMatrixCoordinator(hass, client, entry)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator, client


@pytest.mark.asyncio
async def test_set_input_edid_tracks_current_profile(hass) -> None:
    """async_set_input_edid should record what was last applied."""
    coordinator, client = _coordinator_with_stubbed_refresh(hass)

    await coordinator.async_set_input_edid(3, 6)

    client.set_input_edid_profile.assert_awaited_once_with(3, 6)
    coordinator.async_request_refresh.assert_awaited_once()
    assert coordinator.get_current_edid_profile(3) == 6
    assert coordinator.get_current_edid_profile(4) is None


@pytest.mark.asyncio
async def test_reset_all_edid_clears_tracked_profiles(hass) -> None:
    """Factory reset should forget optimistic per-input state."""
    coordinator, client = _coordinator_with_stubbed_refresh(hass)
    coordinator._current_edid_profile = {1: 3, 2: 6}

    await coordinator.async_reset_all_edid()

    client.reset_all_edid.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()
    assert coordinator.get_current_edid_profile(1) is None
    assert coordinator.get_current_edid_profile(2) is None


@pytest.mark.asyncio
async def test_copy_edid_forgets_tracked_profile(hass) -> None:
    """Copying a display EDID invalidates the cached profile number."""
    coordinator, client = _coordinator_with_stubbed_refresh(hass)
    coordinator._current_edid_profile = {5: 2}

    await coordinator.async_copy_edid_from_output(3, 5)

    client.copy_output_edid_to_input.assert_awaited_once_with(3, 5)
    coordinator.async_request_refresh.assert_awaited_once()
    assert coordinator.get_current_edid_profile(5) is None
