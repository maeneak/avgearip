"""Switch entities for AVGear Matrix Switcher controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NUM_INPUTS, CONF_NUM_OUTPUTS, NUM_INPUTS, NUM_OUTPUTS
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
    num_inputs = int(entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS))
    num_outputs = int(entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

    entities: list[SwitchEntity] = [
        AVGearPanelLockSwitch(coordinator),
        AVGearStandbySwitch(coordinator),
    ]
    entities.extend(
        AVGearInputHDCPSwitch(coordinator, n) for n in range(1, num_inputs + 1)
    )
    entities.extend(
        AVGearOutputHDCPSwitch(coordinator, n) for n in range(1, num_outputs + 1)
    )

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


class AVGearInputHDCPSwitch(AVGearBaseEntity, SwitchEntity):
    """Toggle HDCP compliance on an input (%9978. HDCPEN setting)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: AVGearMatrixCoordinator, input_num: int) -> None:
        """Initialize the input HDCP switch."""
        super().__init__(coordinator)
        self._input_num = input_num
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_input_{input_num}_hdcp"

    @property
    def name(self) -> str:
        """Return a dynamic name using the input's custom name."""
        return f"{self.coordinator.get_input_name(self._input_num)} HDCP"

    @property
    def is_on(self) -> bool:
        """Return True when HDCP is enabled on this input."""
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.input_hdcp.get(self._input_num))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable HDCP on this input."""
        await self.coordinator.async_set_input_hdcp(self._input_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable HDCP on this input."""
        await self.coordinator.async_set_input_hdcp(self._input_num, False)


class AVGearOutputHDCPSwitch(AVGearBaseEntity, SwitchEntity):
    """Toggle HDCP compliance on an output."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: AVGearMatrixCoordinator, output_num: int) -> None:
        """Initialize the output HDCP switch."""
        super().__init__(coordinator)
        self._output_num = output_num
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_output_{output_num}_hdcp"
        self._attr_name = f"Output {output_num} HDCP"

    @property
    def is_on(self) -> bool:
        """Return True when HDCP is reported enabled on this output."""
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.output_hdcp.get(self._output_num))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable HDCP on this output."""
        await self.coordinator.async_set_output_hdcp(self._output_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable HDCP on this output."""
        await self.coordinator.async_set_output_hdcp(self._output_num, False)
