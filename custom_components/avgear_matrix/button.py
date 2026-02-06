"""Button entities for AVGear Matrix Switcher."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AVGearConnectionError
from .const import DOMAIN
from .coordinator import AVGearMatrixCoordinator

if TYPE_CHECKING:
    from . import AVGearMatrixConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVGearMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVGear Matrix button entities."""
    coordinator = entry.runtime_data

    entities: list[ButtonEntity] = [
        AVGearSavePresetButton(coordinator, entry),
        AVGearAllThroughButton(coordinator, entry),
        AVGearAllOffButton(coordinator, entry),
    ]

    async_add_entities(entities)


class AVGearSavePresetButton(CoordinatorEntity[AVGearMatrixCoordinator], ButtonEntity):
    """Button to save current state to the selected preset."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "save_preset"
    _attr_icon = "mdi:bookmark-plus"

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_save_preset"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    async def async_press(self) -> None:
        """Save current routing to the selected preset."""
        preset = self.coordinator.current_preset
        if preset is None:
            _LOGGER.warning("No preset selected, cannot save")
            return

        try:
            await self.coordinator.async_save_preset(preset)
        except AVGearConnectionError as err:
            _LOGGER.error("Failed to save preset %d: %s", preset, err)


class AVGearAllThroughButton(CoordinatorEntity[AVGearMatrixCoordinator], ButtonEntity):
    """Button to route all inputs to corresponding outputs."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_all_through"
        self._attr_name = "All Through"
        self._attr_icon = "mdi:swap-horizontal"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_all_through()


class AVGearAllOffButton(CoordinatorEntity[AVGearMatrixCoordinator], ButtonEntity):
    """Button to switch off all outputs."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_all_off"
        self._attr_name = "All Off"
        self._attr_icon = "mdi:power-off"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_all_off()
