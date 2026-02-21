"""Tests for AVGear config and reconfigure flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.data_entry_flow import FlowResultType

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.avgear_matrix.const import (
    CONF_DEVICE_UID,
    CONF_HOST,
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    CONF_PORT,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_user_flow_creates_entry_with_device_uid(hass) -> None:
    """User flow should create an entry containing a stable device uid."""
    with (
        patch(
            "custom_components.avgear_matrix.config_flow.AVGearMatrixClient.test_connection",
            AsyncMock(return_value={"model": "AVGear Matrix", "firmware": "1.0"}),
        ),
        patch(
            "custom_components.avgear_matrix.config_flow.AVGearMatrixClient.disconnect",
            AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                CONF_HOST: "192.0.2.10",
                CONF_PORT: 4001,
                CONF_NUM_INPUTS: 8,
                CONF_NUM_OUTPUTS: 8,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_UID]


@pytest.mark.asyncio
async def test_user_flow_rejects_duplicate_endpoint(hass) -> None:
    """User flow should reject an endpoint already used by another entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid-existing",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: "uid-existing",
        },
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_reconfigure_updates_endpoint_and_preserves_device_uid(hass) -> None:
    """Reconfigure should update host/port but keep the device uid stable."""
    device_uid = "uid-reconfig"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=device_uid,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: device_uid,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.avgear_matrix.config_flow.AVGearMatrixClient.test_connection",
            AsyncMock(return_value={"model": "AVGear Matrix", "firmware": "1.1"}),
        ),
        patch(
            "custom_components.avgear_matrix.config_flow.AVGearMatrixClient.disconnect",
            AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={
                CONF_HOST: "192.0.2.11",
                CONF_PORT: 4001,
                CONF_NUM_INPUTS: 8,
                CONF_NUM_OUTPUTS: 8,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.0.2.11"
    assert entry.data[CONF_DEVICE_UID] == device_uid


@pytest.mark.asyncio
async def test_reconfigure_rejects_conflicting_endpoint(hass) -> None:
    """Reconfigure should fail if target endpoint is used by another entry."""
    first = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid-first",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: "uid-first",
        },
    )
    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="uid-second",
        data={
            CONF_HOST: "192.0.2.20",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: "uid-second",
        },
    )
    first.add_to_hass(hass)
    second.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": first.entry_id},
        data={
            CONF_HOST: "192.0.2.20",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert first.data[CONF_HOST] == "192.0.2.10"
