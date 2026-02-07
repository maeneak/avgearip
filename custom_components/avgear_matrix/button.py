"""Button entities for AVGear Matrix Switcher."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AVGearConnectionError
from .coordinator import AVGearBaseEntity, AVGearMatrixCoordinator

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
        AVGearSavePresetButton(coordinator),
        AVGearAllThroughButton(coordinator),
        AVGearAllOffButton(coordinator),
    ]

    async_add_entities(entities)


class AVGearSavePresetButton(AVGearBaseEntity, ButtonEntity):
    """Button to save current state to the selected preset."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Save Preset"
    _attr_icon = "mdi:bookmark-plus"

    def __init__(self, coordinator: AVGearMatrixCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_save_preset"

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


class AVGearAllThroughButton(AVGearBaseEntity, ButtonEntity):
    """Button to route all inputs to corresponding outputs."""

    _attr_name = "All Through"
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coordinator: AVGearMatrixCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_all_through"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_all_through()


class AVGearAllOffButton(AVGearBaseEntity, ButtonEntity):
    """Button to switch off all outputs."""

    _attr_name = "All Off"
    _attr_icon = "mdi:power-off"

    def __init__(self, coordinator: AVGearMatrixCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_all_off"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_all_off()
