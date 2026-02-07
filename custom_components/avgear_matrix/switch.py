"""Switch entities for AVGear Matrix Switcher controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AVGearBaseEntity, AVGearMatrixCoordinator

if TYPE_CHECKING:
    from . import AVGearMatrixConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVGearMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVGear Matrix switch entities."""
    coordinator = entry.runtime_data

    entities: list[SwitchEntity] = [
        AVGearPanelLockSwitch(coordinator),
        AVGearStandbySwitch(coordinator),
    ]

    async_add_entities(entities)


class AVGearPanelLockSwitch(AVGearBaseEntity, SwitchEntity):
    """Switch to control panel lock."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AVGearMatrixCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_panel_lock"
        self._attr_name = "Panel Lock"
        self._attr_icon = "mdi:lock"

    @property
    def is_on(self) -> bool:
        """Return true if panel is locked."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.locked

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the panel."""
        await self.coordinator.async_set_panel_lock(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the panel."""
        await self.coordinator.async_set_panel_lock(False)


class AVGearStandbySwitch(AVGearBaseEntity, SwitchEntity):
    """Switch to control standby mode."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AVGearMatrixCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_standby"
        self._attr_name = "Standby"
        self._attr_icon = "mdi:power-standby"

    @property
    def is_on(self) -> bool:
        """Return true if in standby mode."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.power_state in ("STANDBY", "PWOFF")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enter standby mode."""
        await self.coordinator.async_set_standby(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Exit standby mode."""
        await self.coordinator.async_set_standby(False)
