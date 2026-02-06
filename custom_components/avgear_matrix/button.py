"""Button entities for AVGear Matrix Switcher presets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AVGearConnectionError
from .const import DOMAIN, NUM_PRESETS
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

    entities: list[ButtonEntity] = []

    # Recall preset buttons (0-9)
    for preset in range(NUM_PRESETS):
        entities.append(AVGearRecallPresetButton(coordinator, entry, preset))

    # Save preset buttons (0-9)
    for preset in range(NUM_PRESETS):
        entities.append(AVGearSavePresetButton(coordinator, entry, preset))

    # Utility buttons
    entities.append(AVGearAllThroughButton(coordinator, entry))
    entities.append(AVGearAllOffButton(coordinator, entry))

    async_add_entities(entities)


class AVGearRecallPresetButton(CoordinatorEntity[AVGearMatrixCoordinator], ButtonEntity):
    """Button to recall a preset."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
        preset: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._preset = preset
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_recall_preset_{preset}"
        self._attr_icon = "mdi:bookmark-outline"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        preset_name = self.coordinator.get_preset_name(self._preset)
        return f"{preset_name} Recall"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_recall_preset(self._preset)
        except AVGearConnectionError as err:
            _LOGGER.error("Failed to recall preset %d: %s", self._preset, err)
            # Create persistent notification for user
            self.hass.components.persistent_notification.async_create(
                f"Failed to recall preset {self.coordinator.get_preset_name(self._preset)}: {err}",
                title="AVGear Matrix Error",
                notification_id=f"avgear_preset_recall_{self._preset}_error",
            )


class AVGearSavePresetButton(CoordinatorEntity[AVGearMatrixCoordinator], ButtonEntity):
    """Button to save current state to a preset."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
        preset: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._preset = preset
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_save_preset_{preset}"
        self._attr_icon = "mdi:bookmark-plus"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        preset_name = self.coordinator.get_preset_name(self._preset)
        return f"{preset_name} Save"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_save_preset(self._preset)
            # Create success notification
            self.hass.components.persistent_notification.async_create(
                f"Current configuration saved to preset {self.coordinator.get_preset_name(self._preset)}",
                title="AVGear Matrix",
                notification_id=f"avgear_preset_save_{self._preset}_success",
            )
        except AVGearConnectionError as err:
            _LOGGER.error("Failed to save preset %d: %s", self._preset, err)
            # Create error notification for user
            self.hass.components.persistent_notification.async_create(
                f"Failed to save preset {self.coordinator.get_preset_name(self._preset)}: {err}",
                title="AVGear Matrix Error",
                notification_id=f"avgear_preset_save_{self._preset}_error",
            )


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
        await self.coordinator.client.all_through()
        await self.coordinator.async_request_refresh()


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
        await self.coordinator.client.switch_off_all()
        await self.coordinator.async_request_refresh()
