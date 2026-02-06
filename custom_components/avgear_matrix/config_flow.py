"""Config flow for AVGear Matrix Switcher integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .api import AVGearConnectionError, AVGearMatrixClient
from .const import (
    CONF_HOST,
    CONF_INPUT_NAMES,
    CONF_NUM_INPUTS,
    CONF_NUM_OUTPUTS,
    CONF_PORT,
    CONF_PRESET_NAMES,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_NAME_LENGTH,
    NUM_INPUTS,
    NUM_OUTPUTS,
    NUM_PRESETS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_NUM_INPUTS, default=NUM_INPUTS): vol.All(
            int, vol.Range(min=1, max=32)
        ),
        vol.Required(CONF_NUM_OUTPUTS, default=NUM_OUTPUTS): vol.All(
            int, vol.Range(min=1, max=32)
        ),
    }
)


class AVGearMatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AVGear Matrix Switcher."""

    VERSION = 4

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            num_inputs = user_input[CONF_NUM_INPUTS]
            num_outputs = user_input[CONF_NUM_OUTPUTS]

            # Set unique ID based on host:port
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            # Test connection
            client = AVGearMatrixClient(host, port, num_inputs, num_outputs)
            try:
                info = await client.test_connection()
                await client.disconnect()

                title = info.get("model", "AVGear Matrix") or "AVGear Matrix"
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )
            except AVGearConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            num_inputs = user_input[CONF_NUM_INPUTS]
            num_outputs = user_input[CONF_NUM_OUTPUTS]

            # Test connection
            client = AVGearMatrixClient(host, port, num_inputs, num_outputs)
            try:
                await client.test_connection()
                await client.disconnect()

                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
            except AVGearConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            finally:
                await client.disconnect()

        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST)
                    ): str,
                    vol.Required(
                        CONF_PORT, default=reconfigure_entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_NUM_INPUTS,
                        default=reconfigure_entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS),
                    ): vol.All(int, vol.Range(min=1, max=32)),
                    vol.Required(
                        CONF_NUM_OUTPUTS,
                        default=reconfigure_entry.data.get(CONF_NUM_OUTPUTS, NUM_OUTPUTS),
                    ): vol.All(int, vol.Range(min=1, max=32)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return AVGearMatrixOptionsFlow()


class AVGearMatrixOptionsFlow(OptionsFlow):
    """Handle options flow for AVGear Matrix Switcher."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        num_inputs = self.config_entry.data.get(CONF_NUM_INPUTS, NUM_INPUTS)

        if user_input is not None:
            # Parse and strip all name fields
            input_names = {}
            for i in range(1, num_inputs + 1):
                name = user_input.get(f"input_{i}_name", "").strip()
                if name:
                    input_names[str(i)] = name

            preset_names = {}
            for i in range(NUM_PRESETS):
                name = user_input.get(f"preset_{i}_name", "").strip()
                if name:
                    preset_names[str(i)] = name

            # Check for reserved or duplicate input names (would cause routing ambiguity)
            input_name_values = list(input_names.values())
            if any(name.strip().casefold() == "off" for name in input_name_values):
                errors["base"] = "reserved_input_name"
            elif len(input_name_values) != len(set(input_name_values)):
                errors["base"] = "duplicate_input_names"

            # Check for duplicate preset names (would cause selection ambiguity)
            preset_name_values = list(preset_names.values())
            if not errors and len(preset_name_values) != len(set(preset_name_values)):
                errors["base"] = "duplicate_preset_names"

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                        CONF_INPUT_NAMES: input_names,
                        CONF_PRESET_NAMES: preset_names,
                    },
                )

        # Get current options
        current_options = self.config_entry.options

        current_input_names = dict(current_options.get(CONF_INPUT_NAMES, {}))
        current_preset_names = dict(current_options.get(CONF_PRESET_NAMES, {}))
        current_interval = current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        # Populate defaults from user_input if re-showing form after error
        if user_input is not None:
            current_interval = user_input.get(CONF_SCAN_INTERVAL, current_interval)
            for i in range(1, num_inputs + 1):
                val = user_input.get(f"input_{i}_name", "").strip()
                if val:
                    current_input_names[str(i)] = val
            for i in range(NUM_PRESETS):
                val = user_input.get(f"preset_{i}_name", "").strip()
                if val:
                    current_preset_names[str(i)] = val

        # Name validator: enforce max length
        name_validator = vol.All(str, vol.Length(max=MAX_NAME_LENGTH))

        # Build schema with all name fields
        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                int, vol.Range(min=5, max=300)
            ),
        }

        # Add input name fields with placeholders
        for i in range(1, num_inputs + 1):
            default_name = current_input_names.get(str(i), "")
            schema_dict[vol.Optional(
                f"input_{i}_name",
                default=default_name,
                description={"suggested_value": default_name or f"Input {i}"},
            )] = name_validator

        # Add preset name fields with placeholders
        for i in range(NUM_PRESETS):
            default_name = current_preset_names.get(str(i), "")
            schema_dict[vol.Optional(
                f"preset_{i}_name",
                default=default_name,
                description={"suggested_value": default_name or f"Preset {i}"},
            )] = name_validator

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
