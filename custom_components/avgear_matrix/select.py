"""Select entities for AVGear Matrix Switcher."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    EDID_PROFILES,
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

    num_inputs = int(entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS))
    num_outputs = int(entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

    entities: list[SelectEntity] = [
        AVGearMatrixOutputSelect(coordinator, output_num)
        for output_num in range(1, num_outputs + 1)
    ]

    # Add "Route to All" select entity
    entities.append(AVGearRouteToAllSelect(coordinator))

    # Add preset select entity
    entities.append(AVGearPresetSelect(coordinator))

    # One EDID profile select per input
    entities.extend(
        AVGearInputEDIDSelect(coordinator, input_num)
        for input_num in range(1, num_inputs + 1)
    )

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


class AVGearInputEDIDSelect(AVGearBaseEntity, SelectEntity):
    """Select entity to choose an input's EDID profile.

    State is optimistic — the firmware has no reliable readback for the
    active slot on an input, so ``current_option`` reflects whatever profile
    the integration last applied (stored on the coordinator). After a HA
    restart the state is unknown until the user picks a profile.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:video-input-hdmi"
    _attr_options = list(EDID_PROFILES.values())

    def __init__(
        self,
        coordinator: AVGearMatrixCoordinator,
        input_num: int,
    ) -> None:
        """Initialize the EDID select."""
        super().__init__(coordinator)
        self._input_num = input_num
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_input_{input_num}_edid"

    @property
    def name(self) -> str:
        """Return a dynamic name based on the input's custom name."""
        return f"{self.coordinator.get_input_name(self._input_num)} EDID"

    @property
    def current_option(self) -> str | None:
        """Return the last-applied profile name, if known."""
        profile = self.coordinator.get_current_edid_profile(self._input_num)
        if profile is None:
            return None
        return EDID_PROFILES.get(profile)

    async def async_select_option(self, option: str) -> None:
        """Apply a built-in EDID profile to this input."""
        for slot, label in EDID_PROFILES.items():
            if label == option:
                await self.coordinator.async_set_input_edid(self._input_num, slot)
                self.async_write_ha_state()
                return
        _LOGGER.error("Invalid EDID profile option: %s", option)
