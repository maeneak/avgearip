"""Switch entities for AVGear Matrix Switcher controls."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    """Set up AVGear Matrix switch entities."""
    coordinator = entry.runtime_data

    entities: list[SwitchEntity] = [
        AVGearPanelLockSwitch(coordinator, entry),
        AVGearStandbySwitch(coordinator, entry),
    ]

    async_add_entities(entities)


class AVGearPanelLockSwitch(CoordinatorEntity[AVGearMatrixCoordinator], SwitchEntity):
    """Switch to control panel lock."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_panel_lock"
        self._attr_name = "Panel Lock"
        self._attr_icon = "mdi:lock"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class AVGearStandbySwitch(CoordinatorEntity[AVGearMatrixCoordinator], SwitchEntity):
    """Switch to control standby mode."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_standby"
        self._attr_name = "Standby"
        self._attr_icon = "mdi:power-standby"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
