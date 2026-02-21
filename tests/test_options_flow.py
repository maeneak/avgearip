"""Tests for AVGear options flow validation behavior."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.data_entry_flow import FlowResultType

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.avgear_matrix.const import (
    CONF_DEVICE_UID,
    CONF_HOST,
    CONF_INPUT_NAMES,
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    CONF_PORT,
    CONF_PRESET_NAMES,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)


def _create_entry(num_inputs: int = 2, options: dict | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 4001,
            CONF_NUM_INPUTS: num_inputs,
            CONF_NUM_OUTPUTS: 8,
            CONF_DEVICE_UID: "uid-options",
        },
        options=options or {},
    )


def _field_default(schema: vol.Schema, field_name: str) -> str:
    for marker in schema.schema:
        if marker.schema == field_name:
            default = marker.default
            return default() if callable(default) else default
    raise KeyError(field_name)


@pytest.mark.asyncio
async def test_options_reject_case_insensitive_duplicate_input_names(hass) -> None:
    """Input names must be unique irrespective of case."""
    entry = _create_entry()
    entry.add_to_hass(hass)

    init_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 30,
            "input_1_name": "Source",
            "input_2_name": "source",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "duplicate_input_names"


@pytest.mark.asyncio
async def test_options_reject_reserved_off_input_name(hass) -> None:
    """Input name 'Off' is reserved (case-insensitive)."""
    entry = _create_entry()
    entry.add_to_hass(hass)

    init_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 30,
            "input_1_name": "oFf",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "reserved_input_name"


@pytest.mark.asyncio
async def test_options_preserve_cleared_fields_after_validation_error(hass) -> None:
    """Clearing a field should remain cleared when form is re-rendered."""
    entry = _create_entry(
        options={
            CONF_SCAN_INTERVAL: 30,
            CONF_INPUT_NAMES: {"1": "Blu-ray", "2": "Apple TV"},
            CONF_PRESET_NAMES: {"0": "Cinema"},
        }
    )
    entry.add_to_hass(hass)

    init_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 30,
            "input_1_name": "",
            "input_2_name": "Apple TV",
            "preset_0_name": "Movie",
            "preset_1_name": "movie",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "duplicate_preset_names"
    assert _field_default(result["data_schema"], "input_1_name") == ""
    assert _field_default(result["data_schema"], "input_2_name") == "Apple TV"
