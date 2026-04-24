"""DataUpdateCoordinator for AVGear Matrix Switcher."""

from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .api import AVGearCommandError, AVGearConnectionError, AVGearMatrixClient, MatrixStatus
from .const import (
    CONF_DEVICE_UID,
    CONF_INPUT_NAMES,
    CONF_PRESET_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AVGearMatrixCoordinator(DataUpdateCoordinator[MatrixStatus]):
    """Coordinator for polling AVGear Matrix status."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: AVGearMatrixClient,
        config_entry: ConfigEntry,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )
        self.client = client
        self._device_info: dict[str, str] = {}
        self._current_preset: int | None = None
        # Input EDID profile tracking is optimistic: the firmware has no
        # reliable readback telling us which slot is active, so we remember
        # what we last set and surface that to the select entity. Missing
        # keys mean "unknown" — we never store None explicitly.
        self._current_edid_profile: dict[int, int] = {}

    @property
    def device_info(self) -> dict[str, str]:
        """Return device info."""
        return self._device_info

    @property
    def current_preset(self) -> int | None:
        """Return the currently selected preset."""
        return self._current_preset

    def async_reset_current_preset(self) -> None:
        """Reset preset tracking.
        
        Call this after device reconnection or when preset state may be
        out of sync (e.g., controlled by another client).
        """
        self._current_preset = None

    async def async_setup(self) -> None:
        """Set up the coordinator and fetch initial device info."""
        try:
            info = await self.client.test_connection()
            self._device_info = {
                "model": info.get("model", "AVGear Matrix"),
                "firmware": info.get("firmware", "Unknown"),
            }
        except AVGearConnectionError as err:
            _LOGGER.error("Failed to connect to AVGear Matrix: %s", err)
            raise

    async def _async_update_data(self) -> MatrixStatus:
        """Fetch data from the matrix."""
        try:
            status = await self.client.get_status()
        except (AVGearConnectionError, AVGearCommandError) as err:
            raise UpdateFailed(f"Error communicating with AVGear Matrix: {err}") from err

        # Best-effort supplementary data — don't fail the whole update.
        # Each query is isolated so a firmware quirk in one response cannot
        # take the whole integration offline.
        for label, fetch in (
            ("power state", self.client.get_power_state),
            ("lock status", self.client.get_lock_status),
            ("input HDCP setting", self.client.get_input_hdcp),
            ("output HDCP capability", self.client.get_output_hdcp),
            ("input HDCP active", self.client.get_input_hdcp_active),
            ("input connection", self.client.get_input_connection),
            ("output connection", self.client.get_output_connection),
            ("output resolution", self.client.get_output_resolution),
        ):
            try:
                await fetch()
            except (AVGearConnectionError, AVGearCommandError):
                _LOGGER.debug("Failed to fetch %s", label)

        return status

    async def async_route_input(self, input_num: int, output_num: int) -> None:
        """Route an input to an output and refresh."""
        await self.client.route_input_to_output(input_num, output_num)
        await self.async_request_refresh()

    async def async_route_input_to_all(self, input_num: int) -> None:
        """Route an input to all outputs and refresh."""
        await self.client.route_input_to_all(input_num)
        await self.async_request_refresh()

    async def async_switch_off_output(self, output_num: int) -> None:
        """Switch off an output and refresh."""
        await self.client.switch_off_output(output_num)
        await self.async_request_refresh()

    async def async_recall_preset(self, preset: int) -> None:
        """Recall a preset and refresh."""
        await self.client.recall_preset(preset)
        self._current_preset = preset
        await self.async_request_refresh()

    async def async_save_preset(self, preset: int) -> None:
        """Save current state to a preset."""
        await self.client.save_preset(preset)

    async def async_set_panel_lock(self, locked: bool) -> None:
        """Set panel lock state."""
        if locked:
            await self.client.lock_panel()
        else:
            await self.client.unlock_panel()
        await self.async_request_refresh()

    async def async_all_through(self) -> None:
        """Route all inputs to corresponding outputs and refresh."""
        await self.client.all_through()
        await self.async_request_refresh()

    async def async_all_off(self) -> None:
        """Switch off all outputs and refresh."""
        await self.client.switch_off_all()
        await self.async_request_refresh()

    async def async_set_standby(self, standby: bool) -> None:
        """Set standby state."""
        if standby:
            await self.client.standby()
        else:
            await self.client.power_on()
        await self.async_request_refresh()

    # --- HDCP wrappers ---

    async def async_set_input_hdcp(self, input_num: int | str, compliant: bool) -> None:
        """Set input HDCP compliance and refresh."""
        await self.client.set_input_hdcp(input_num, compliant)
        await self.async_request_refresh()

    async def async_set_output_hdcp(self, output_num: int | str, compliant: bool) -> None:
        """Set output HDCP compliance and refresh."""
        await self.client.set_output_hdcp(output_num, compliant)
        await self.async_request_refresh()

    async def async_auto_hdcp(self) -> None:
        """Run Auto HDCP management."""
        await self.client.auto_hdcp()
        await self.async_request_refresh()

    # --- EDID wrappers ---

    async def async_set_input_edid(self, input_num: int, profile: int) -> None:
        """Set input EDID to a built-in slot and remember the choice."""
        await self.client.set_input_edid_profile(input_num, profile)
        self._current_edid_profile[input_num] = profile
        await self.async_request_refresh()

    async def async_copy_edid_from_output(self, output_num: int, input_num: int) -> None:
        """Copy display EDID from an output onto an input."""
        await self.client.copy_output_edid_to_input(output_num, input_num)
        # No reliable readback; forget any cached profile for this input.
        self._current_edid_profile.pop(input_num, None)
        await self.async_request_refresh()

    async def async_force_input_pcm(self, input_num: int) -> None:
        """Force input EDID audio section to PCM."""
        await self.client.force_input_edid_pcm(input_num)
        await self.async_request_refresh()

    async def async_reset_all_edid(self) -> None:
        """Factory-restore all input EDIDs."""
        await self.client.reset_all_edid()
        self._current_edid_profile.clear()
        await self.async_request_refresh()

    def get_current_edid_profile(self, input_num: int) -> int | None:
        """Return the last profile the integration set on an input, if any."""
        return self._current_edid_profile.get(input_num)

    def get_input_name(self, input_num: int) -> str:
        """Get custom name for an input or return default."""
        input_names = self.config_entry.options.get(CONF_INPUT_NAMES, {})
        return input_names.get(str(input_num), f"Input {input_num}")

    def get_preset_name(self, preset_num: int) -> str:
        """Get custom name for a preset or return default."""
        preset_names = self.config_entry.options.get(CONF_PRESET_NAMES, {})
        return preset_names.get(str(preset_num), f"Preset {preset_num}")


class AVGearBaseEntity(CoordinatorEntity[AVGearMatrixCoordinator]):
    """Base entity for AVGear Matrix devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AVGearMatrixCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        device_uid = coordinator.config_entry.data.get(CONF_DEVICE_UID, coordinator.config_entry.entry_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_uid)},
        )
