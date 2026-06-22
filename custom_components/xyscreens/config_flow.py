"""Config flow for XY Screens integration."""

import logging
from typing import Any

import voluptuous as vol
from xyscreens import XYScreens

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SerialPortSelector,
)

from .const import (
    CONF_ADDRESS_SEE_MAX,
    CONF_ADDRESS_XYSCREENS,
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


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT, default=""): SerialPortSelector(),
        vol.Required(CONF_ADDRESS, default=""): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(
                        value=CONF_ADDRESS_XYSCREENS,
                        label=f"{CONF_ADDRESS_XYSCREENS} (XY Screens)",
                    ),
                    SelectOptionDict(
                        value=CONF_ADDRESS_SEE_MAX,
                        label=f"{CONF_ADDRESS_SEE_MAX} (See Max)",
                    ),
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
OPTIONS_SCHEMA = vol.Schema(
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


def validate_address(address) -> bool:
    """Validates the address."""
    try:
        address = bytes.fromhex(address)
        address = address.hex()

        if len(address) != 6:
            return False
    except ValueError:
        return False

    return True


class XYScreensConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for XY Screens."""

    VERSION = 2
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate user input.
            DATA_SCHEMA(user_input)

            serial_port = user_input[CONF_SERIAL_PORT]
            address = user_input[CONF_ADDRESS]

            # Validate the address.
            if not validate_address(address):
                errors[CONF_ADDRESS] = "invalid_address"

            # Make sure the serial port and address is not already used.
            await self.async_set_unique_id(f"{serial_port}-{address}")
            self._abort_if_unique_id_configured()

            # Test if we can connect to the device.
            time_open = user_input[CONF_TIME_OPEN]
            screen = XYScreens(serial_port, address, time_open)
            if not await screen.async_test_connection():
                errors[CONF_SERIAL_PORT] = "cannot_connect"

            if not errors:
                title = f"{serial_port} {address.upper()}"
                data = {
                    CONF_SERIAL_PORT: serial_port,
                    CONF_ADDRESS: address,
                    CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                }
                options = {
                    CONF_TIME_OPEN: user_input[CONF_TIME_OPEN],
                    CONF_TIME_CLOSE: user_input[CONF_TIME_CLOSE],
                    CONF_INVERTED: user_input[CONF_INVERTED],
                }
                return self.async_create_entry(title=title, data=data, options=options)

        # Combine user input with schema.
        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input or {})

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            OPTIONS_SCHEMA(user_input)
            return self.async_create_entry(title="", data=user_input)

        # Combine user input with schema.
        data_schema = self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA, user_input or self.config_entry.options
        )

        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        return self.async_show_form(
            step_id=device_type,
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_projector_screen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)

    async def async_step_projector_lift(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)
