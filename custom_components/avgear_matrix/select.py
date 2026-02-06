"""Select entities for AVGear Matrix Switcher outputs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUM_INPUTS, NUM_OUTPUTS
from .coordinator import AVGearMatrixCoordinator

if TYPE_CHECKING:
    from . import AVGearMatrixConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVGearMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AVGear Matrix select entities."""
    coordinator = entry.runtime_data

    entities: list[SelectEntity] = [
        AVGearMatrixOutputSelect(coordinator, entry, output_num)
        for output_num in range(1, NUM_OUTPUTS + 1)
    ]

    # Add "Route to All" select entity
    entities.append(AVGearRouteToAllSelect(coordinator, entry))

    async_add_entities(entities)


class AVGearMatrixOutputSelect(CoordinatorEntity[AVGearMatrixCoordinator], SelectEntity):
    """Select entity for an AVGear Matrix output."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
        output_num: int,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._output_num = output_num
        self._entry = entry

        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_output_{output_num}"
        self._attr_translation_key = "matrix_output"

    @property
    def options(self) -> list[str]:
        """Return available input options dynamically."""
        options = [self.coordinator.get_input_name(i) for i in range(1, NUM_INPUTS + 1)]
        options.append("Off")
        return options

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.coordinator.get_output_name(self._output_num)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected input."""
        if self.coordinator.data is None:
            return None

        input_num = self.coordinator.data.outputs.get(self._output_num)
        if input_num is None or input_num == 0:
            return "Off"
        if 1 <= input_num <= NUM_INPUTS:
            return self.coordinator.get_input_name(input_num)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected input."""
        if option == "Off":
            await self.coordinator.async_switch_off_output(self._output_num)
        else:
            # Find input number by matching name
            input_num = None
            for i in range(1, NUM_INPUTS + 1):
                if self.coordinator.get_input_name(i) == option:
                    input_num = i
                    break
            
            if input_num:
                await self.coordinator.async_route_input(input_num, self._output_num)
            else:
                _LOGGER.error("Invalid input option: %s", option)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class AVGearRouteToAllSelect(CoordinatorEntity[AVGearMatrixCoordinator], SelectEntity):
    """Select entity to route an input to all outputs."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        entry: AVGearMatrixConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._entry = entry

        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_route_to_all"
        self._attr_translation_key = "route_to_all_outputs"
        self._attr_icon = "mdi:video-input-hdmi"

    @property
    def options(self) -> list[str]:
        """Return available input options dynamically."""
        return [self.coordinator.get_input_name(i) for i in range(1, NUM_INPUTS + 1)]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current option if all outputs share the same input."""
        if self.coordinator.data is None:
            return None

        # Check if all outputs are routed to the same input
        outputs = self.coordinator.data.outputs
        if not outputs:
            return None

        first_input = outputs.get(1)
        if first_input is None:
            return None

        # Check if all outputs match
        for out in range(1, NUM_OUTPUTS + 1):
            if outputs.get(out) != first_input:
                return None  # Not all same, no selection shown

        if 1 <= first_input <= NUM_INPUTS:
            return self.coordinator.get_input_name(first_input)
        return None

    async def async_select_option(self, option: str) -> None:
        """Route selected input to all outputs."""
        # Find input number by matching name
        input_num = None
        for i in range(1, NUM_INPUTS + 1):
            if self.coordinator.get_input_name(i) == option:
                input_num = i
                break
        
        if input_num:
            await self.coordinator.client.route_input_to_all(input_num)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Invalid input option: %s", option)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
