"""Config flow for XY Screens integration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import test_serial_port, test_tcp_connection
from .const import (
    CONF_ADDRESS,
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_NETWORK,
    CONF_CONNECTION_TYPE_SERIAL,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_TYPE_PROJECTOR_LIFT,
    CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
    CONF_HOST,
    CONF_INVERTED,
    CONF_PORT,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class XYScreensConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for XY Screens."""

    VERSION = 2
    MINOR_VERSION = 2

    _step_setup_connection_schema: vol.Schema

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_connection_type(user_input)

    async def async_step_connection_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the connection type selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            connection_type = user_input.get(CONF_CONNECTION_TYPE)
            if connection_type in (
                CONF_CONNECTION_TYPE_SERIAL,
                CONF_CONNECTION_TYPE_NETWORK,
            ):
                return await self.async_step_setup_connection(user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONNECTION_TYPE, default=CONF_CONNECTION_TYPE_SERIAL
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=CONF_CONNECTION_TYPE_SERIAL,
                                label="Serial Port (RS485 USB adapter)",
                            ),
                            SelectOptionDict(
                                value=CONF_CONNECTION_TYPE_NETWORK,
                                label="Network (RS485-to-Ethernet converter)",
                            ),
                        ],
                        translation_key=CONF_CONNECTION_TYPE,
                    )
                ),
            }
        )

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)

        return self.async_show_form(
            step_id="connection_type",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_setup_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the setup connection step (serial or network)."""
        errors: dict[str, str] = {}

        # Get connection type from previous step or user input
        connection_type = CONF_CONNECTION_TYPE_SERIAL
        if user_input is not None:
            connection_type = user_input.get(
                CONF_CONNECTION_TYPE, CONF_CONNECTION_TYPE_SERIAL
            )

        if user_input is not None and CONF_ADDRESS in user_input:
            title, data, options = await self.validate_input_setup_connection(
                user_input, errors
            )

            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        # Build schema based on connection type
        schema_fields: dict = {}

        if connection_type == CONF_CONNECTION_TYPE_SERIAL:
            ports = await self.hass.async_add_executor_job(
                serial.tools.list_ports.comports
            )
            list_of_ports = {}
            for port in ports:
                list_of_ports[port.device] = (
                    f"{port}, s/n: {port.serial_number or 'n/a'}"
                    + (f" - {port.manufacturer}" if port.manufacturer else "")
                )

            schema_fields[vol.Required(CONF_SERIAL_PORT, default="")] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=k, label=v)
                        for k, v in list_of_ports.items()
                    ],
                    custom_value=True,
                    sort=True,
                )
            )
        else:
            schema_fields[vol.Required(CONF_HOST, default="")] = TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            )
            schema_fields[vol.Required(CONF_PORT, default=9997)] = NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    mode=NumberSelectorMode.BOX,
                )
            )

        # Add hidden connection type field to preserve selection
        schema_fields[
            vol.Required(CONF_CONNECTION_TYPE, default=connection_type)
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(
                        value=connection_type,
                        label=(
                            "Serial Port"
                            if connection_type == CONF_CONNECTION_TYPE_SERIAL
                            else "Network"
                        ),
                    ),
                ],
            )
        )

        # Common fields
        schema_fields.update(
            {
                vol.Required(CONF_ADDRESS, default=""): SelectSelector(
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
                    CONF_DEVICE_TYPE, default=CONF_DEVICE_TYPE_PROJECTOR_SCREEN
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
                vol.Required(CONF_TIME_OPEN, default=1): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfTime.SECONDS,
                    )
                ),
                vol.Required(CONF_TIME_CLOSE, default=1): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfTime.SECONDS,
                    )
                ),
                vol.Required(CONF_INVERTED, default=False): BooleanSelector(),
            }
        )

        self._step_setup_connection_schema = vol.Schema(schema_fields)

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(
                self._step_setup_connection_schema, user_input
            )
        else:
            data_schema = self._step_setup_connection_schema

        return self.async_show_form(
            step_id="setup_connection",
            data_schema=data_schema,
            errors=errors,
        )

    # pylint: disable=W0613
    async def validate_input_setup_connection(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Validate the user input and create data."""
        self._step_setup_connection_schema(data)

        connection_type = data.get(CONF_CONNECTION_TYPE)
        connection_string = ""

        if connection_type == CONF_CONNECTION_TYPE_SERIAL:
            serial_port = data.get(CONF_SERIAL_PORT)

            if serial_port is None:
                raise vol.error.RequiredFieldInvalid("No serial port configured")

            serial_port = await self.hass.async_add_executor_job(
                get_serial_by_id, serial_port
            )

            if not Path(serial_port).exists():
                errors[CONF_SERIAL_PORT] = "nonexisting_serial_port"

            connection_string = serial_port

            if errors.get(CONF_SERIAL_PORT) is None:
                try:
                    await test_serial_port(serial_port)
                except serial.SerialException:
                    errors["base"] = "cannot_connect"

        elif connection_type == CONF_CONNECTION_TYPE_NETWORK:
            host = data.get(CONF_HOST)
            port = data.get(CONF_PORT)

            if not host:
                errors[CONF_HOST] = "invalid_host"
            if not port or port < 1 or port > 65535:
                errors[CONF_PORT] = "invalid_port"

            connection_string = f"{host}:{int(port)}"

            if not errors.get(CONF_HOST) and not errors.get(CONF_PORT):
                try:
                    await test_tcp_connection(host, int(port))
                except Exception:
                    errors["base"] = "cannot_connect"

        # Validate the address.
        address = data.get(CONF_ADDRESS)
        try:
            address = bytes.fromhex(address)
            address = address.hex()

            if len(address) != 6:
                errors[CONF_ADDRESS] = "invalid_address"
        except ValueError:
            errors[CONF_ADDRESS] = "invalid_address"

        await self.async_set_unique_id(f"{connection_string}-{address}")
        self._abort_if_unique_id_configured()

        entry_data = {
            CONF_CONNECTION_TYPE: connection_type,
            CONF_ADDRESS: address,
            CONF_DEVICE_TYPE: data[CONF_DEVICE_TYPE],
        }

        if connection_type == CONF_CONNECTION_TYPE_SERIAL:
            entry_data[CONF_SERIAL_PORT] = connection_string
        else:
            entry_data[CONF_HOST] = data[CONF_HOST]
            entry_data[CONF_PORT] = data[CONF_PORT]

        return (
            f"{connection_string} {address.upper()}",
            entry_data,
            {
                CONF_TIME_OPEN: data[CONF_TIME_OPEN],
                CONF_TIME_CLOSE: data[CONF_TIME_CLOSE],
                CONF_INVERTED: data[CONF_INVERTED],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return XYScreensOptionsFlowHandler()


class XYScreensOptionsFlowHandler(OptionsFlow):
    """Handle the options flow for XY Screens."""

    _OPTIONS_SCHEMA = vol.Schema(
        {
            vol.Required(
                CONF_TIME_OPEN,
                default=1,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
            vol.Required(
                CONF_TIME_CLOSE,
                default=1,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
            vol.Required(
                CONF_INVERTED,
                default=False,
            ): BooleanSelector(),
        }
    )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._OPTIONS_SCHEMA(user_input)
            return self.async_create_entry(title="", data=user_input)

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(
                self._OPTIONS_SCHEMA, user_input
            )
        else:
            data_schema = self.add_suggested_values_to_schema(
                self._OPTIONS_SCHEMA, self.config_entry.options
            )

        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        return self.async_show_form(
            step_id=device_type,
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_projector_screen(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)

    async def async_step_projector_lift(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not Path(by_id).is_dir():
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
