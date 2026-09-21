"""Config flow for XY Screens integration."""

from typing import Any, override

import probatio
from xyscreens import XYScreens

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, UnitOfTime
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

DEVICE_TYPE_TITLES = {
    CONF_DEVICE_TYPE_PROJECTOR_SCREEN: "Projector Screen",
    CONF_DEVICE_TYPE_PROJECTOR_LIFT: "Projector Lift",
}

ADDRESS_SELECTOR = SelectSelector(
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
)

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_SERIAL_PORT, default=""): SerialPortSelector(),
        probatio.Required(CONF_ADDRESS, default=""): ADDRESS_SELECTOR,
        probatio.Required(
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
        probatio.Required(CONF_TIME_OPEN, default=1): NumberSelector(
            NumberSelectorConfig(
                min=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        probatio.Required(CONF_TIME_CLOSE, default=1): NumberSelector(
            NumberSelectorConfig(
                min=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        probatio.Required(CONF_INVERTED, default=False): BooleanSelector(),
    }
)
RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_SERIAL_PORT, default=""): SerialPortSelector(),
        probatio.Required(CONF_ADDRESS, default=""): ADDRESS_SELECTOR,
        probatio.Required(
            CONF_TIME_OPEN,
            default=1,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        probatio.Required(
            CONF_TIME_CLOSE,
            default=1,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        probatio.Required(
            CONF_INVERTED,
            default=False,
        ): BooleanSelector(),
    }
)


def validate_address(address: str) -> bool:
    """Validates the address."""
    try:
        if len(bytes.fromhex(address)) != 3:
            return False
    except ValueError:
        return False

    return True


class XYScreensConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for XY Screens."""

    VERSION = 2
    MINOR_VERSION = 2

    async def _async_validate_and_test(
        self,
        user_input: dict[str, Any],
        device_type: str | None = None,
    ) -> tuple[dict[str, str], str, dict[str, Any], dict[str, Any]]:
        """Validate the input and test the connection."""
        errors: dict[str, str] = {}
        serial_port = user_input[CONF_SERIAL_PORT]
        address = user_input[CONF_ADDRESS]
        device_type = user_input.get(CONF_DEVICE_TYPE, device_type)

        if device_type is None:
            errors["base"] = "unknown"

        # Validate the address.
        if not validate_address(address):
            errors[CONF_ADDRESS] = "invalid_address"

        # Test if we can connect to the device.
        time_open = user_input[CONF_TIME_OPEN]
        screen = XYScreens(serial_port, bytes.fromhex(address), time_open)
        if not await screen.async_test_connection():
            errors[CONF_SERIAL_PORT] = "cannot_connect"

        data = {
            CONF_SERIAL_PORT: serial_port,
            CONF_ADDRESS: address,
            CONF_DEVICE_TYPE: device_type,
        }
        options = {
            CONF_TIME_OPEN: user_input[CONF_TIME_OPEN],
            CONF_TIME_CLOSE: user_input[CONF_TIME_CLOSE],
            CONF_INVERTED: user_input[CONF_INVERTED],
        }

        return errors, data, options

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial_port = user_input[CONF_SERIAL_PORT]
            address = user_input[CONF_ADDRESS]
            device_type = user_input[CONF_DEVICE_TYPE]

            # Make sure the serial port + address combination is not already used.
            self._async_abort_entries_match(
                {CONF_SERIAL_PORT: serial_port, CONF_ADDRESS: address}
            )

            errors, data, options = await self._async_validate_and_test(
                user_input
            )
            title = f"{DEVICE_TYPE_TITLES[device_type]} {address.upper()}"
            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        # Combine user input with schema.
        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input or {})

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfigure flow."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        device_type = reconfigure_entry.data[CONF_DEVICE_TYPE]

        if user_input is not None:
            serial_port = user_input[CONF_SERIAL_PORT]
            address = user_input[CONF_ADDRESS]

            # Make sure the new serial port + address combination is not already used.
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if (
                    entry.entry_id != reconfigure_entry.entry_id
                    and entry.data.get(CONF_SERIAL_PORT) == serial_port
                    and entry.data.get(CONF_ADDRESS) == address
                ):
                    return self.async_abort(reason="already_configured")

            errors, data, options = await self._async_validate_and_test(
                user_input, device_type
            )

            if not errors:
                # Keep the entry's existing title instead of regenerating it, so
                # a title the user customized isn't overwritten on reconfigure.
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=reconfigure_entry.title,
                    data=data,
                    options=options,
                    reason="reconfigure_successful",
                )

        # Combine the current entry data with schema.
        data_schema = self.add_suggested_values_to_schema(
            RECONFIGURE_SCHEMA,
            user_input or {**reconfigure_entry.data, **reconfigure_entry.options},
        )

        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={"title": reconfigure_entry.title},
            data_schema=data_schema,
            errors=errors,
        )
