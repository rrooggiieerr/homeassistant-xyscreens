"""Config flow for XY Screens integration."""

from __future__ import annotations

import logging
import os
from typing import Any, Tuple

import homeassistant.helpers.config_validation as cv
import serial.tools.list_ports
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from . import test_serial_port
from .const import (
    CONF_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_TYPE_PROJECTOR_LIFT,
    CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
    CONF_INVERTED,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class XYScreensConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for XY Screens."""

    VERSION = 3

    _step_setup_serial_schema: vol.Schema

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_setup_serial(user_input)

    async def async_step_setup_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the setup serial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title, data, options = await self.validate_input_setup_serial(
                user_input, errors
            )

            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        if user_input is None:
            user_input = {}

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = {}
        for port in ports:
            list_of_ports[port.device] = (
                f"{port}, s/n: {port.serial_number or 'n/a'}"
                + (f" - {port.manufacturer}" if port.manufacturer else "")
            )

        self._step_setup_serial_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERIAL_PORT, default=user_input.get(CONF_SERIAL_PORT)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=k, label=v)
                            for k, v in list_of_ports.items()
                        ],
                        custom_value=True,
                        sort=True,
                    )
                ),
                vol.Required(
                    CONF_ADDRESS, default=user_input.get(CONF_ADDRESS)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value="AAEEEE", label="AAEEEE (XY Screens)"
                            ),
                            SelectOptionDict(value="EEEEEE", label="EEEEEE (See Max)"),
                        ],
                        custom_value=True,
                        sort=True,
                    )
                ),
                vol.Required(
                    CONF_DEVICE_TYPE,
                    default=user_input.get(
                        CONF_DEVICE_TYPE, CONF_DEVICE_TYPE_PROJECTOR_SCREEN
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
                                label=CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
                            ),
                            SelectOptionDict(
                                value=CONF_DEVICE_TYPE_PROJECTOR_LIFT,
                                label=CONF_DEVICE_TYPE_PROJECTOR_LIFT,
                            ),
                        ],
                        translation_key=CONF_DEVICE_TYPE,
                    )
                ),
                vol.Required(
                    CONF_TIME_OPEN, default=user_input.get(CONF_TIME_OPEN, 1)
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_TIME_CLOSE, default=user_input.get(CONF_TIME_CLOSE, 1)
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_INVERTED, default=user_input.get(CONF_INVERTED, False)
                ): bool,
            }
        )

        _LOGGER.debug("XXXXX")
        data_schema = self.add_suggested_values_to_schema(
            self._step_setup_serial_schema, user_input
        )

        return self.async_show_form(
            step_id="setup_serial",
            data_schema=data_schema,
            errors=errors,
        )

    # pylint: disable=W0613
    async def validate_input_setup_serial(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> Tuple[str, dict[str, Any], dict[str, Any]]:
        """
        Validate the user input and create data.

        Data has the keys from _step_setup_serial_schema with values provided by the user.
        """
        # Validate the data can be used to set up a connection.
        self._step_setup_serial_schema(data)

        serial_port = data.get(CONF_SERIAL_PORT)

        if serial_port is None:
            raise vol.error.RequiredFieldInvalid("No serial port configured")

        serial_port = await self.hass.async_add_executor_job(
            get_serial_by_id, serial_port
        )

        # Test if the device exists
        if not os.path.exists(serial_port):
            errors[CONF_SERIAL_PORT] = "nonexisting_serial_port"
            # raise vol.error.PathInvalid(f"Device {serial_port} does not exists")

        address = data.get(CONF_ADDRESS)
        try:
            address = bytes.fromhex(address)
            address = address.hex()

            if len(address) != 6:
                errors[CONF_ADDRESS] = "invalid_address"
        except ValueError:
            errors[CONF_ADDRESS] = "invalid_address"

        # Make sure the serial port and address is not already used by an other integration.
        await self.async_set_unique_id(f"{serial_port}-{address}")
        self._abort_if_unique_id_configured()

        if errors.get(CONF_SERIAL_PORT) is None:
            # Test if we can connect to the device.
            _LOGGER.debug("Test if we can connect to the device.")
            try:
                await test_serial_port(serial_port)
            except serial.SerialException:
                errors["base"] = "cannot_connect"

        # Return title, data and options
        return (
            f"{serial_port} {address.upper()}",
            {
                CONF_SERIAL_PORT: serial_port,
                CONF_ADDRESS: address,
                CONF_DEVICE_TYPE: data[CONF_DEVICE_TYPE],
            },
            {
                CONF_TIME_OPEN: data[CONF_TIME_OPEN],
                CONF_TIME_CLOSE: data[CONF_TIME_CLOSE],
                CONF_INVERTED: data[CONF_INVERTED],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return XYScreensOptionsFlowHandler(config_entry)


class XYScreensOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the config flow for XY Screens."""

    _options_schema: vol.Schema

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        self._options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TIME_OPEN,
                    default=self.config_entry.options.get(CONF_TIME_OPEN, 0),
                ): cv.positive_int,
                vol.Required(
                    CONF_TIME_CLOSE,
                    default=self.config_entry.options.get(CONF_TIME_CLOSE, 0),
                ): cv.positive_int,
                vol.Required(
                    CONF_INVERTED,
                    default=self.config_entry.options.get(CONF_INVERTED, False),
                ): bool,
            }
        )

        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        if device_type == CONF_DEVICE_TYPE_PROJECTOR_LIFT:
            return await self.async_step_projector_lift(user_input)

        return await self.async_step_projector_screen(user_input)

    async def async_step_projector_screen(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._options_schema(user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id=CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
            data_schema=self._options_schema,
            errors=errors,
        )

    async def async_step_projector_lift(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._options_schema(user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id=CONF_DEVICE_TYPE_PROJECTOR_LIFT,
            data_schema=self._options_schema,
            errors=errors,
        )


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
