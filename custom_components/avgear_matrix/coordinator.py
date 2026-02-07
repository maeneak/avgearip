"""DataUpdateCoordinator for AVGear Matrix Switcher."""

from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .api import AVGearConnectionError, AVGearMatrixClient, MatrixStatus
from .const import CONF_INPUT_NAMES, CONF_PRESET_NAMES, DEFAULT_SCAN_INTERVAL, DOMAIN

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
        except AVGearConnectionError as err:
            raise UpdateFailed(f"Error communicating with AVGear Matrix: {err}") from err

        # Best-effort supplementary data — don't fail the whole update
        try:
            await self.client.get_power_state()
        except AVGearConnectionError:
            _LOGGER.debug("Failed to fetch power state")
        try:
            await self.client.get_lock_status()
        except AVGearConnectionError:
            _LOGGER.debug("Failed to fetch lock status")

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        )
