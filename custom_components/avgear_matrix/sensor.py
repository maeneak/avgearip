"""Sensor entities for AVGear Matrix Switcher diagnostics.

Currently provides one per-output resolution sensor. Disabled by default —
users enable only the outputs they want to track.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NUM_OUTPUTS, NUM_OUTPUTS
from .coordinator import AVGearBaseEntity, AVGearMatrixCoordinator

if TYPE_CHECKING:
    from . import AVGearMatrixConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVGearMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVGear Matrix diagnostic sensors."""
    coordinator = entry.runtime_data
    num_outputs = int(entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

    async_add_entities(
        AVGearOutputResolutionSensor(coordinator, n)
        for n in range(1, num_outputs + 1)
    )


class AVGearOutputResolutionSensor(AVGearBaseEntity, SensorEntity):
    """Report the resolution the matrix is driving on an output (%9976.)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:television"

    def __init__(self, coordinator: AVGearMatrixCoordinator, output_num: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._output_num = output_num
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_output_{output_num}_resolution"
        )
        self._attr_name = f"Output {output_num} Resolution"

    @property
    def native_value(self) -> str | None:
        """Return the last-reported output resolution string."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.output_resolution.get(self._output_num)
