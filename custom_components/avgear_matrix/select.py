"""Select entities for AVGear Matrix Switcher."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    NUM_INPUTS,
    NUM_OUTPUTS,
    NUM_PRESETS,
)
from .coordinator import AVGearBaseEntity, AVGearMatrixCoordinator

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

    num_outputs = int(entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

    entities: list[SelectEntity] = [
        AVGearMatrixOutputSelect(coordinator, output_num)
        for output_num in range(1, num_outputs + 1)
    ]

    # Add "Route to All" select entity
    entities.append(AVGearRouteToAllSelect(coordinator))

    # Add preset select entity
    entities.append(AVGearPresetSelect(coordinator))

    async_add_entities(entities)


class AVGearMatrixOutputSelect(AVGearBaseEntity, SelectEntity):
    """Select entity for an AVGear Matrix output."""

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._output_num = output_num
        self._num_inputs = int(coordinator.config_entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS))

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_output_{output_num}"
        self._attr_name = f"Output {output_num}"

    @property
    def options(self) -> list[str]:
        """Return available input options dynamically."""
        options = [self.coordinator.get_input_name(i) for i in range(1, self._num_inputs + 1)]
        options.append("Off")
        return options

    @property
    def current_option(self) -> str | None:
        """Return the current selected input."""
        if self.coordinator.data is None:
            return None

        input_num = self.coordinator.data.outputs.get(self._output_num)
        if input_num is None or input_num == 0:
            return "Off"
        if 1 <= input_num <= self._num_inputs:
            return self.coordinator.get_input_name(input_num)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected input."""
        if option == "Off":
            await self.coordinator.async_switch_off_output(self._output_num)
        else:
            # Find input number by matching name
            input_num = None
            for i in range(1, self._num_inputs + 1):
                if self.coordinator.get_input_name(i) == option:
                    input_num = i
                    break

            if input_num:
                await self.coordinator.async_route_input(input_num, self._output_num)
            else:
                _LOGGER.error("Invalid input option: %s", option)


class AVGearRouteToAllSelect(AVGearBaseEntity, SelectEntity):
    """Select entity to route an input to all outputs."""

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._num_inputs = int(coordinator.config_entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS))
        self._num_outputs = int(coordinator.config_entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

        # Entity attributes
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_route_to_all"
        self._attr_name = "Route to All Outputs"
        self._attr_icon = "mdi:video-input-hdmi"

    @property
    def options(self) -> list[str]:
        """Return available input options dynamically."""
        return [self.coordinator.get_input_name(i) for i in range(1, self._num_inputs + 1)]

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
        for out in range(1, self._num_outputs + 1):
            if outputs.get(out) != first_input:
                return None  # Not all same, no selection shown

        if 1 <= first_input <= self._num_inputs:
            return self.coordinator.get_input_name(first_input)
        return None

    async def async_select_option(self, option: str) -> None:
        """Route selected input to all outputs."""
        # Find input number by matching name
        input_num = None
        for i in range(1, self._num_inputs + 1):
            if self.coordinator.get_input_name(i) == option:
                input_num = i
                break

        if input_num:
            await self.coordinator.async_route_input_to_all(input_num)
        else:
            _LOGGER.error("Invalid input option: %s", option)


class AVGearPresetSelect(AVGearBaseEntity, SelectEntity):
    """Select entity to recall a preset."""

    _attr_name = "Preset"
    _attr_icon = "mdi:bookmark-outline"

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_preset"

    @property
    def options(self) -> list[str]:
        """Return available preset options dynamically."""
        return [self.coordinator.get_preset_name(i) for i in range(NUM_PRESETS)]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected preset."""
        preset = self.coordinator.current_preset
        if preset is None:
            return None
        return self.coordinator.get_preset_name(preset)

    async def async_select_option(self, option: str) -> None:
        """Recall the selected preset."""
        # Find preset number by matching name
        preset_num = None
        for i in range(NUM_PRESETS):
            if self.coordinator.get_preset_name(i) == option:
                preset_num = i
                break

        if preset_num is not None:
            await self.coordinator.async_recall_preset(preset_num)
        else:
            _LOGGER.error("Invalid preset option: %s", option)
