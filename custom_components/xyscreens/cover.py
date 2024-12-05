"""The XY Screens cover entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from xyscreens import XYScreens, XYScreensState

from .const import (
    CONF_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_TYPE_PROJECTOR_LIFT,
    CONF_INVERTED,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=W0613
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the XY Screens cover."""
    async_add_entities(
        [
            XYScreensCover(
                config_entry.entry_id,
                config_entry.data.get(CONF_SERIAL_PORT),
                bytes.fromhex(config_entry.data.get(CONF_ADDRESS, "AAEEEE")),
                config_entry.data.get(CONF_DEVICE_TYPE),
                config_entry.options.get(CONF_TIME_OPEN),
                config_entry.options.get(CONF_TIME_CLOSE),
                config_entry.options.get(CONF_INVERTED),
            )
        ]
    )


class XYScreensCover(CoverEntity, RestoreEntity):
    """The XY Screens cover."""

    _attr_assumed_state = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_should_poll = False

    _attr_is_closed = False

    def __init__(
        self,
        config_entry_id: str,
        serial_port: str,
        address: bytes,
        device_type: str,
        time_open: int,
        time_close: int,
        inverted: bool,
    ) -> None:
        """Initialize the screen."""
        if device_type == CONF_DEVICE_TYPE_PROJECTOR_LIFT:
            translation_key = "projector_lift"
        else:
            translation_key = "projector_screen"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry_id)},
            translation_key=translation_key,
            manufacturer="XY Screens",
        )
        self._attr_unique_id = config_entry_id

        if inverted:
            translation_key += "_inverted"

        self.entity_description = CoverEntityDescription(
            key="projector_screen",
            has_entity_name=True,
            translation_key=translation_key,
            name=None,  # Inherit the device name
        )

        self._screen = XYScreens(serial_port, address, time_open, time_close)

        self._inverted = inverted

    async def async_added_to_hass(self) -> None:
        """Called when sensor is added to Home Assistant."""
        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            position = last_state.attributes.get(ATTR_CURRENT_POSITION)
            _LOGGER.debug("Last screen position: %5.1f %%", position)
            if not self._inverted:
                self._screen.restore_position(100 - position)
            else:
                self._screen.restore_position(position)
            self._attr_current_cover_position = position
            if position == 0:
                self._attr_is_closed = True

        self._screen.add_callback(self._callback)

    @callback
    def _callback(self, state: XYScreensState, position: float):
        """Callback to be called by XYScreens library whenever a state changes."""
        if not self._inverted:
            position = 100 - self._screen.position()
        else:
            position = self._screen.position()
        self._attr_current_cover_position = round(position)

        if state == XYScreensState.UP:
            self._attr_is_closing = False
            self._attr_is_closed = self._inverted
            self._attr_is_opening = False
        elif state == XYScreensState.UPWARD:
            self._attr_is_closing = self._inverted
            self._attr_is_closed = False
            self._attr_is_opening = not self._inverted
        elif state == XYScreensState.STOPPED:
            self._attr_is_closing = False
            self._attr_is_closed = False
            self._attr_is_opening = False
        elif state == XYScreensState.DOWNWARD:
            self._attr_is_closing = not self._inverted
            self._attr_is_closed = False
            self._attr_is_opening = self._inverted
        elif state == XYScreensState.DOWN:
            self._attr_is_closing = False
            self._attr_is_closed = not self._inverted
            self._attr_is_opening = False

        self.async_write_ha_state()

    async def _async_open_cover(self, **kwargs: Any) -> None:
        await self._screen.async_up()

    async def _async_close_cover(self, **kwargs: Any) -> None:
        await self._screen.async_down()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if not self._inverted:
            await self._async_open_cover()
        else:
            await self._async_close_cover()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if not self._inverted:
            await self._async_close_cover()
        else:
            await self._async_open_cover()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._screen.async_stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self.current_cover_position == position:
            return

        if not self._inverted:
            await self._screen.async_set_position(100 - position)
        else:
            await self._screen.async_set_position(position)
