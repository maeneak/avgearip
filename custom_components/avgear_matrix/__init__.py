"""The AVGear Matrix Switcher integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeAlias, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .api import AVGearCommandError, AVGearConnectionError, AVGearMatrixClient
from .const import (
    CONF_DEVICE_UID,
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

PLATFORMS: list[Platform] = [
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

if TYPE_CHECKING:
    AVGearMatrixConfigEntry: TypeAlias = ConfigEntry[AVGearMatrixCoordinator]
else:
    AVGearMatrixConfigEntry = ConfigEntry

SERVICE_SAVE_PRESET = "save_preset"
SERVICE_COPY_EDID_FROM_OUTPUT = "copy_edid_from_output"
SERVICE_FORCE_INPUT_PCM = "force_input_pcm"
SERVICE_DUMP_EDID = "dump_edid"

ATTR_PRESET = "preset"
ATTR_DEVICE_ID = "device_id"
ATTR_INPUT = "input"
ATTR_OUTPUT = "output"
ATTR_SOURCE = "source"
ATTR_NUMBER = "number"

DUMP_SOURCE_INPUT = "input"
DUMP_SOURCE_OUTPUT = "output"
DUMP_SOURCE_SLOT = "slot"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AVGear Matrix integration."""

    def _resolve_entry(device_id: str | None) -> AVGearMatrixConfigEntry:
        """Resolve which loaded matrix a service call targets.

        If ``device_id`` is given, look it up. Otherwise fall back to the sole
        loaded entry, raising if multiple entries are loaded and none was
        specified.
        """
        loaded_entries: list[AVGearMatrixConfigEntry] = cast(
            list[AVGearMatrixConfigEntry],
            [
                entry
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.state is ConfigEntryState.LOADED
            ],
        )
        if not loaded_entries:
            raise ServiceValidationError("No AVGear Matrix devices are loaded")

        if device_id:
            device_registry = dr.async_get(hass)
            device = device_registry.async_get(device_id)
            if device:
                for entry in loaded_entries:
                    if entry.entry_id in device.config_entries:
                        return entry
            raise ServiceValidationError("Selected device is not an AVGear Matrix")

        if len(loaded_entries) == 1:
            return loaded_entries[0]

        raise ServiceValidationError(
            "Multiple AVGear Matrix devices loaded; specify a device_id"
        )

    async def handle_save_preset(call: ServiceCall) -> None:
        """Handle the save_preset service call."""
        target_entry = _resolve_entry(call.data.get(ATTR_DEVICE_ID))
        await target_entry.runtime_data.async_save_preset(call.data[ATTR_PRESET])

    async def handle_copy_edid_from_output(call: ServiceCall) -> None:
        """Copy a display's EDID onto an input."""
        target_entry = _resolve_entry(call.data.get(ATTR_DEVICE_ID))
        await target_entry.runtime_data.async_copy_edid_from_output(
            int(call.data[ATTR_OUTPUT]), int(call.data[ATTR_INPUT])
        )

    async def handle_force_input_pcm(call: ServiceCall) -> None:
        """Force an input's EDID audio section to PCM."""
        target_entry = _resolve_entry(call.data.get(ATTR_DEVICE_ID))
        await target_entry.runtime_data.async_force_input_pcm(
            int(call.data[ATTR_INPUT])
        )

    async def handle_dump_edid(call: ServiceCall) -> dict[str, Any]:
        """Return the raw EDID bytes from an input, output, or built-in slot."""
        target_entry = _resolve_entry(call.data.get(ATTR_DEVICE_ID))
        source = call.data[ATTR_SOURCE]
        number = int(call.data[ATTR_NUMBER])
        client = target_entry.runtime_data.client

        dumpers = {
            DUMP_SOURCE_INPUT: client.dump_input_edid,
            DUMP_SOURCE_OUTPUT: client.dump_output_edid,
            DUMP_SOURCE_SLOT: client.dump_builtin_edid,
        }
        try:
            raw = await dumpers[source](number)
        except (AVGearConnectionError, AVGearCommandError) as err:
            raise ServiceValidationError(f"Failed to read EDID: {err}") from err

        return {
            "hex": raw.hex(),
            "length": len(raw),
            "source": source,
            "number": number,
        }

    if not hass.services.has_service(DOMAIN, SERVICE_SAVE_PRESET):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SAVE_PRESET,
            handle_save_preset,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_PRESET): vol.All(int, vol.Range(min=0, max=9)),
                    vol.Optional(ATTR_DEVICE_ID): str,
                }
            ),
            supports_response=False,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_COPY_EDID_FROM_OUTPUT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_COPY_EDID_FROM_OUTPUT,
            handle_copy_edid_from_output,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_INPUT): vol.All(int, vol.Range(min=1, max=32)),
                    vol.Required(ATTR_OUTPUT): vol.All(int, vol.Range(min=1, max=32)),
                    vol.Optional(ATTR_DEVICE_ID): str,
                }
            ),
            supports_response=SupportsResponse.NONE,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_FORCE_INPUT_PCM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_FORCE_INPUT_PCM,
            handle_force_input_pcm,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_INPUT): vol.All(int, vol.Range(min=1, max=32)),
                    vol.Optional(ATTR_DEVICE_ID): str,
                }
            ),
            supports_response=SupportsResponse.NONE,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_DUMP_EDID):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DUMP_EDID,
            handle_dump_edid,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_SOURCE): vol.In(
                        [DUMP_SOURCE_INPUT, DUMP_SOURCE_OUTPUT, DUMP_SOURCE_SLOT]
                    ),
                    vol.Required(ATTR_NUMBER): vol.All(int, vol.Range(min=1, max=32)),
                    vol.Optional(ATTR_DEVICE_ID): str,
                }
            ),
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AVGearMatrixConfigEntry) -> bool:
    """Set up AVGear Matrix Switcher from a config entry."""
    host = entry.data[CONF_HOST]
    port = int(entry.data[CONF_PORT])
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    num_inputs = int(entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS))
    num_outputs = int(entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

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
    device_uid = entry.data.get(CONF_DEVICE_UID, entry.entry_id)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_uid)},
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

    if config_entry.version < 3:
        # Migrate to v3: strip output_names, keep input_names and preset_names
        old_options = {**config_entry.options}

        # Collect input names from any version
        input_names: dict[str, str] = old_options.get(CONF_INPUT_NAMES, {})

        # Collect preset names from any version
        preset_names: dict[str, str] = old_options.get(CONF_PRESET_NAMES, {})

        new_options = {
            CONF_SCAN_INTERVAL: int(old_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
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
