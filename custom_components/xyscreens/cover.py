"""The XY Screens cover entity."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

# import serial
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from xyscreens import XYScreens

from .const import CONF_SERIAL_PORT, CONF_TIME_CLOSE, CONF_TIME_OPEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCREEN_OPENED_ICON = "mdi:projector-screen-variant-outline"
SCREEN_CLOSED_ICON = "mdi:projector-screen-variant-off-outline"


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
                config_entry.data.get(CONF_SERIAL_PORT),
                config_entry.options.get(CONF_TIME_OPEN, None),
                config_entry.options.get(CONF_TIME_CLOSE, None),
            )
        ]
    )


class XYScreensCover(CoverEntity, RestoreEntity):
    """The XY Screens cover."""

    _attr_assumed_state = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_should_poll = False

    _attr_current_cover_position = 100
    _attr_is_closed = False
    _attr_is_closing = False
    _attr_is_opening = False

    _unsubscribe_updater = None

    entity_description = CoverEntityDescription(
        key="projector_screen",
        device_class=CoverDeviceClass.SHADE,
        icon=SCREEN_OPENED_ICON,
        has_entity_name=True,
        name=None,
    )

    def __init__(self, serial_port, time_open, time_close) -> None:
        """Initialize the screen."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_port)},
            name="Projector Screen",
            manufacturer="XY Screens",
        )
        self._attr_unique_id = serial_port

        self._screen = XYScreens(serial_port, time_open, time_close)

    async def async_added_to_hass(self) -> None:
        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            position = last_state.attributes.get(ATTR_CURRENT_POSITION)
            _LOGGER.debug("Last screen position: %5.1f %%", position)
            self._screen.set_position(100 - position)
            self._attr_current_cover_position = position
            if position == 0:
                self._attr_is_closed = True

            # Icon of the entity.
            if position > 50:
                self._attr_icon = SCREEN_CLOSED_ICON

    async def async_update(self) -> None:
        """Calculate and update cover position."""
        position = 100 - self._screen.position()
        _LOGGER.debug("Screen position: %5.1f %%", position)
        state = self._screen.state()

        if state == XYScreens.STATE_UP:
            self._attr_is_closing = False
            self._attr_is_closed = False
            self._attr_is_opening = False
            self.stop_updater()
        elif state == XYScreens.STATE_UPWARD:
            self._attr_is_closing = False
            self._attr_is_closed = False
            self._attr_is_opening = True
        elif state == XYScreens.STATE_STOPPED:
            self._attr_is_closing = False
            self._attr_is_closed = False
            self._attr_is_opening = False
            self.stop_updater()
        elif state == XYScreens.STATE_DOWNWARD:
            self._attr_is_closing = True
            self._attr_is_closed = False
            self._attr_is_opening = False
        elif state == XYScreens.STATE_DOWN:
            self._attr_is_closing = False
            self._attr_is_closed = True
            self._attr_is_opening = False
            self.stop_updater()

        # Icon of the entity.
        if position <= 50.0:
            self._attr_icon = SCREEN_OPENED_ICON
        else:
            self._attr_icon = SCREEN_CLOSED_ICON

        self._attr_current_cover_position = int(position)

    def start_updater(self):
        """Start the updater to update Home Assistant while cover is moving."""
        if self._unsubscribe_updater is None:
            _LOGGER.debug("Start update listener")
            self._unsubscribe_updater = async_track_time_interval(
                self.hass, self.updater_hook, timedelta(seconds=0.1)
            )

    @callback
    # pylint: disable=W0613
    def updater_hook(self, now):
        """Call for the updater."""
        _LOGGER.debug("Updater hook")
        self.async_schedule_update_ha_state(True)

    def stop_updater(self):
        """Stop the updater."""
        if self._unsubscribe_updater is not None:
            _LOGGER.debug("Stop update listener")
            self._unsubscribe_updater()
            self._unsubscribe_updater = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if await self.hass.async_add_executor_job(self._screen.up):
            self.start_updater()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if await self.hass.async_add_executor_job(self._screen.down):
            self.start_updater()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if await self.hass.async_add_executor_job(self._screen.stop):
            self.stop_updater()
