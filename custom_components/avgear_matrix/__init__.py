"""The AVGear Matrix Switcher integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .api import AVGearConnectionError, AVGearMatrixClient
from .const import (
    CONF_HOST,
    CONF_INPUT_NAMES,
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    CONF_PORT,
    CONF_PRESET_NAMES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NUM_INPUTS,
    NUM_OUTPUTS,
)
from .coordinator import AVGearMatrixCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.BUTTON, Platform.SWITCH]

AVGearMatrixConfigEntry = ConfigEntry[AVGearMatrixCoordinator]

SERVICE_SAVE_PRESET = "save_preset"
ATTR_PRESET = "preset"
ATTR_DEVICE_ID = "device_id"


async def async_setup_entry(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> bool:
    """Set up AVGear Matrix Switcher from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    num_inputs = entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS)
    num_outputs = entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS)

    client = AVGearMatrixClient(host, port, num_inputs, num_outputs)

    coordinator = AVGearMatrixCoordinator(hass, client, entry, scan_interval)

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

    # Register services
    async def handle_save_preset(call: ServiceCall) -> None:
        """Handle the save_preset service call."""
        preset = call.data[ATTR_PRESET]
        device_id = call.data.get(ATTR_DEVICE_ID)

        loaded_entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]

        if not loaded_entries:
            raise ServiceValidationError("No AVGear Matrix devices are loaded")

        target_entry: AVGearMatrixConfigEntry | None = None

        if device_id:
            device_registry = dr.async_get(hass)
            device = device_registry.async_get(device_id)
            if device:
                for entry in loaded_entries:
                    if entry.entry_id in device.config_entries:
                        target_entry = entry
                        break
            if target_entry is None:
                raise ServiceValidationError("Selected device is not an AVGear Matrix")
        elif len(loaded_entries) == 1:
            target_entry = loaded_entries[0]
        else:
            raise ServiceValidationError(
                "Multiple AVGear Matrix devices loaded; specify a device_id"
            )

        await target_entry.runtime_data.async_save_preset(preset)

    if not hass.services.has_service(DOMAIN, SERVICE_SAVE_PRESET):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SAVE_PRESET,
            handle_save_preset,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_PRESET): vol.All(
                        int, vol.Range(min=0, max=9)
                    ),
                    vol.Optional(ATTR_DEVICE_ID): str,
                }
            ),
            supports_response=False,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.client.disconnect()

    # Unregister service if no more loaded entries remain
    loaded_entries = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and e.entry_id != entry.entry_id
    ]
    if unload_ok and not loaded_entries:
        hass.services.async_remove(DOMAIN, SERVICE_SAVE_PRESET)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < 3:
        # Migrate to v3: strip output_names, keep input_names and preset_names
        old_options = {**config_entry.options}

        # Collect input names from any version
        input_names: dict[str, str] = old_options.get(CONF_INPUT_NAMES, {})

        # Collect preset names from any version
        preset_names: dict[str, str] = old_options.get(CONF_PRESET_NAMES, {})

        new_options = {
            CONF_SCAN_INTERVAL: old_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_INPUT_NAMES: input_names,
            CONF_PRESET_NAMES: preset_names,
        }

        hass.config_entries.async_update_entry(
            config_entry, options=new_options, version=3
        )

    if config_entry.version < 4:
        # Migrate to v4: add num_inputs and num_outputs to data
        new_data = {**config_entry.data}
        if CONF_NUM_INPUTS not in new_data:
            new_data[CONF_NUM_INPUTS] = NUM_INPUTS
        if CONF_NUM_OUTPUTS not in new_data:
            new_data[CONF_NUM_OUTPUTS] = NUM_OUTPUTS

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=4
        )

    _LOGGER.debug("Migration to version %s successful", config_entry.version)
    return True
