"""Tests for integration setup and service behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.avgear_matrix import (
    ATTR_DEVICE_ID,
    ATTR_PRESET,
    SERVICE_SAVE_PRESET,
    async_setup,
    async_unload_entry,
)
from custom_components.avgear_matrix.const import (
    CONF_DEVICE_UID,
    CONF_HOST,
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    CONF_PORT,
    DOMAIN,
)


def _patch_loaded_entries(monkeypatch, hass, entries) -> None:
    """Patch config entry lookup used by the save_preset action."""

    def async_entries(domain=None):
        if domain == DOMAIN:
            return entries
        return []

    monkeypatch.setattr(hass.config_entries, "async_entries", async_entries)


@pytest.mark.asyncio
async def test_service_registered_in_async_setup(hass) -> None:
    """The save_preset action should be registered during integration setup."""
    assert not hass.services.has_service(DOMAIN, SERVICE_SAVE_PRESET)

    assert await async_setup(hass, {})
    assert hass.services.has_service(DOMAIN, SERVICE_SAVE_PRESET)


@pytest.mark.asyncio
async def test_save_preset_service_requires_loaded_entries(hass, monkeypatch) -> None:
    """The action should fail clearly when no devices are loaded."""
    await async_setup(hass, {})
    _patch_loaded_entries(monkeypatch, hass, [])

    with pytest.raises(ServiceValidationError, match="No AVGear Matrix devices are loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_PRESET,
            {ATTR_PRESET: 1},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_save_preset_service_requires_target_with_multiple_entries(hass, monkeypatch) -> None:
    """The action should require device_id when multiple devices are loaded."""
    await async_setup(hass, {})
    first = SimpleNamespace(
        entry_id="entry-1",
        state=ConfigEntryState.LOADED,
        runtime_data=SimpleNamespace(async_save_preset=AsyncMock()),
    )
    second = SimpleNamespace(
        entry_id="entry-2",
        state=ConfigEntryState.LOADED,
        runtime_data=SimpleNamespace(async_save_preset=AsyncMock()),
    )
    _patch_loaded_entries(monkeypatch, hass, [first, second])

    with pytest.raises(ServiceValidationError, match="specify a device_id"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_PRESET,
            {ATTR_PRESET: 1},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_save_preset_service_rejects_invalid_device_id(hass, monkeypatch) -> None:
    """The action should validate the selected target device."""
    await async_setup(hass, {})
    entry = SimpleNamespace(
        entry_id="entry-1",
        state=ConfigEntryState.LOADED,
        runtime_data=SimpleNamespace(async_save_preset=AsyncMock()),
    )
    _patch_loaded_entries(monkeypatch, hass, [entry])

    with pytest.raises(ServiceValidationError, match="not an AVGear Matrix"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_PRESET,
            {ATTR_PRESET: 1, ATTR_DEVICE_ID: "missing-device"},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_save_preset_service_calls_single_loaded_entry(hass, monkeypatch) -> None:
    """The action should dispatch to the single loaded entry when unambiguous."""
    await async_setup(hass, {})
    save_mock = AsyncMock()
    entry = SimpleNamespace(
        entry_id="entry-1",
        state=ConfigEntryState.LOADED,
        runtime_data=SimpleNamespace(async_save_preset=save_mock),
    )
    _patch_loaded_entries(monkeypatch, hass, [entry])

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_PRESET,
        {ATTR_PRESET: 7},
        blocking=True,
    )

    save_mock.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_service_remains_registered_after_entry_unload(hass, monkeypatch) -> None:
    """Unloading an entry should not remove the integration-level action."""
    await async_setup(hass, {})
    assert hass.services.has_service(DOMAIN, SERVICE_SAVE_PRESET)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: 8,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: "uid-unload",
        },
    )
    entry.runtime_data = SimpleNamespace(client=SimpleNamespace(disconnect=AsyncMock()))
    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    )

    assert await async_unload_entry(hass, entry)
    assert hass.services.has_service(DOMAIN, SERVICE_SAVE_PRESET)
