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
    CONF_OUTPUT_NAMES,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NUM_OUTPUTS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class AVGearMatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AVGear Matrix Switcher."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Set unique ID based on host:port
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            # Test connection
            client = AVGearMatrixClient(host, port)
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

            # Test connection
            client = AVGearMatrixClient(host, port)
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
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return AVGearMatrixOptionsFlow(config_entry)


class AVGearMatrixOptionsFlow(OptionsFlow):
    """Handle options flow for AVGear Matrix Switcher."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Parse output names from individual fields
            output_names = {}
            for i in range(1, NUM_OUTPUTS + 1):
                name = user_input.get(f"output_{i}_name", f"Output {i}")
                if name and name != f"Output {i}":
                    output_names[str(i)] = name

            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_OUTPUT_NAMES: output_names,
                },
            )

        # Get current options
        current_options = self.config_entry.options
        current_names = current_options.get(CONF_OUTPUT_NAMES, {})
        current_interval = current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        # Build schema with output name fields
        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                int, vol.Range(min=5, max=300)
            ),
        }

        # Add output name fields
        for i in range(1, NUM_OUTPUTS + 1):
            default_name = current_names.get(str(i), f"Output {i}")
            schema_dict[vol.Optional(f"output_{i}_name", default=default_name)] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
