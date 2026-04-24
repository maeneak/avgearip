"""Binary sensor entities for AVGear Matrix Switcher diagnostics.

All entities added here default to ``entity_registry_enabled_default = False``
so a fresh integration install does not spam the device page with dozens of
chatty diagnostic sensors. Users opt in per-entity via the entity settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up AVGear Matrix diagnostic binary sensors."""
    coordinator = entry.runtime_data
    num_inputs = int(entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS))
    num_outputs = int(entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS))

    entities: list[BinarySensorEntity] = []
    for n in range(1, num_inputs + 1):
        entities.append(AVGearInputConnectionSensor(coordinator, n))
        entities.append(AVGearInputHDCPActiveSensor(coordinator, n))
    for n in range(1, num_outputs + 1):
        entities.append(AVGearOutputConnectionSensor(coordinator, n))

    async_add_entities(entities)


class _AVGearDiagnosticBinarySensor(AVGearBaseEntity, BinarySensorEntity):
    """Shared base for diagnostic binary sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False


class AVGearInputConnectionSensor(_AVGearDiagnosticBinarySensor):
    """Is an HDMI cable plugged into this input?"""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AVGearMatrixCoordinator, input_num: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._input_num = input_num
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_input_{input_num}_connected"
        )

    @property
    def name(self) -> str:
        """Return a name based on the input's custom label."""
        return f"{self.coordinator.get_input_name(self._input_num)} Connected"

    @property
    def is_on(self) -> bool | None:
        """Return True when a source is connected."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.input_connected.get(self._input_num)


class AVGearOutputConnectionSensor(_AVGearDiagnosticBinarySensor):
    """Is a display plugged into this output?"""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AVGearMatrixCoordinator, output_num: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._output_num = output_num
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_output_{output_num}_connected"
        )
        self._attr_name = f"Output {output_num} Connected"

    @property
    def is_on(self) -> bool | None:
        """Return True when a display is connected."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.output_connected.get(self._output_num)


class AVGearInputHDCPActiveSensor(_AVGearDiagnosticBinarySensor):
    """Is this input currently carrying an HDCP-encrypted stream (%9973.)?"""

    _attr_icon = "mdi:shield-lock"

    def __init__(self, coordinator: AVGearMatrixCoordinator, input_num: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._input_num = input_num
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_input_{input_num}_hdcp_active"
        )

    @property
    def name(self) -> str:
        """Return a name based on the input's custom label."""
        return f"{self.coordinator.get_input_name(self._input_num)} HDCP Active"

    @property
    def is_on(self) -> bool | None:
        """Return the live HDCP negotiation state."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.input_hdcp_active.get(self._input_num)
