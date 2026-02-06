"""The AVGear Matrix Switcher integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .api import AVGearConnectionError, AVGearMatrixClient
from .const import (
    CONF_HOST,
    CONF_INPUT_NAMES,
    CONF_OUTPUT_NAMES,
    CONF_PORT,
    CONF_PRESET_NAMES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NUM_OUTPUTS,
)
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Migrate v1 -> v2: move individual output_X_name keys to dictionaries
        old_options = {**config_entry.options}
        output_names: dict[str, str] = old_options.get(CONF_OUTPUT_NAMES, {})

        # Check for old flat output_X_name keys
        if not output_names:
            for i in range(1, NUM_OUTPUTS + 1):
                old_key = f"output_{i}_name"
                if old_key in old_options:
                    name = old_options.pop(old_key, "").strip()
                    if name and name != f"Output {i}":
                        output_names[str(i)] = name

        new_options = {
            CONF_SCAN_INTERVAL: old_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_INPUT_NAMES: old_options.get(CONF_INPUT_NAMES, {}),
            CONF_OUTPUT_NAMES: output_names,
            CONF_PRESET_NAMES: old_options.get(CONF_PRESET_NAMES, {}),
        }

        hass.config_entries.async_update_entry(
            config_entry, options=new_options, version=2
        )

    _LOGGER.debug("Migration to version %s successful", config_entry.version)
    return True
