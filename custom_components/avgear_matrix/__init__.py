"""The AVGear Matrix Switcher integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .api import AVGearConnectionError, AVGearMatrixClient
from .const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import AVGearMatrixCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.BUTTON, Platform.SWITCH]

AVGearMatrixConfigEntry = ConfigEntry[AVGearMatrixCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> bool:
    """Set up AVGear Matrix Switcher from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    client = AVGearMatrixClient(host, port)

    coordinator = AVGearMatrixCoordinator(hass, client, scan_interval)

    try:
        await coordinator.async_setup()
    except AVGearConnectionError as err:
        await client.disconnect()
        raise ConfigEntryNotReady(f"Cannot connect to {host}:{port}") from err

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Register device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="AVGear",
        model=coordinator.device_info.get("model", "Matrix Switcher"),
        sw_version=coordinator.device_info.get("firmware"),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.client.disconnect()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
