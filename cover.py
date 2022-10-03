from __future__ import annotations

from datetime import timedelta
import logging
import os
import time
from typing import Any

import serial
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DEVICE_CLASS_SHADE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.const import CONF_COMMAND_CLOSE, CONF_COMMAND_OPEN, CONF_COMMAND_STOP
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    COMMAND_DICT,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the XY Screens cover."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            XYScreensCover(
                config[CONF_SERIAL_PORT],
                config[CONF_TIME_OPEN],
                config[CONF_TIME_CLOSE],
            )
        ]
    )


class XYScreensCover(CoverEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = DEVICE_CLASS_SHADE
    _attr_icon = "mdi:projector-screen-variant"
    _attr_assumed_state = True
    _attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
    _attr_should_poll = False

    _attr_current_cover_position = 100
    _attr_is_closed = False
    _attr_is_closing = False
    _attr_is_opening = False

    _direction = CONF_COMMAND_STOP
    _percentage = 100.0  # 0 is closed, 100 is fully open
    _timestamp = 0
    _unsubscribe_updater = None

    def __init__(self, serial_port, time_open, time_close) -> None:
        """Initialize the cover."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_port)},
            name="Projector Screen",
            manufacturer="XY Screens",
        )
        self._attr_unique_id = serial_port

        self._serial_port = serial_port
        self._time_open = time_open
        self._time_close = time_close

    async def async_added_to_hass(self) -> None:
        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            _LOGGER.debug(
                "Old cover position: %s",
                last_state.attributes.get(ATTR_CURRENT_POSITION),
            )
            self._attr_current_cover_position = last_state.attributes.get(
                ATTR_CURRENT_POSITION
            )
            self._percentage = self._attr_current_cover_position
            if self._percentage == 0:
                self._attr_is_closed = True

    async def async_update(self) -> None:
        if self._direction == CONF_COMMAND_OPEN:
            self._percentage = (
                (time.time() - self._timestamp) / self._time_open
            ) * 100.0
            self._attr_is_closing = False
            self._attr_is_closed = False
            if self._percentage >= 100.0:
                self._direction = CONF_COMMAND_STOP
                self._percentage = 100.0
                self._attr_is_opening = False
            else:
                self._attr_is_opening = True
        elif self._direction == CONF_COMMAND_CLOSE:
            self._percentage = 100.0 - (
                ((time.time() - self._timestamp) / self._time_close) * 100.0
            )
            self._attr_is_opening = False
            if self._percentage <= 0.0:
                self._direction = CONF_COMMAND_STOP
                self._percentage = 0.0
                self._attr_is_closing = False
                self._attr_is_closed = True
            else:
                self._attr_is_closing = True
                self._attr_is_closed = False

        # Icon of the entity.
        if self._percentage <= 50.0:
            self._attr_icon = "mdi:projector-screen-variant-outline"
        else:
            self._attr_icon = "mdi:projector-screen-variant-off-outline"

        self._attr_current_cover_position = int(self._percentage)
        self.async_write_ha_state()

    def start_updater(self):
        """Start the updater to update Home Assistant while cover is moving."""
        if self._unsubscribe_updater is None:
            _LOGGER.debug("start update listener")
            self._unsubscribe_updater = async_track_time_interval(
                self.hass, self.updater_hook, timedelta(seconds=0.1)
            )

    @callback
    def updater_hook(self, now):
        """Call for the updater."""
        _LOGGER.debug("updater hook")
        self.async_schedule_update_ha_state(True)

    def stop_updater(self):
        """Stop the updater."""
        if self._unsubscribe_updater is not None:
            _LOGGER.debug("stop update listener")
            self._unsubscribe_updater()
            self._unsubscribe_updater = None

    def _send_command(self, command: str) -> bool:
        """Execute the actual commands."""
        # Test if the device exists
        if not os.path.exists(self._serial_port):
            _LOGGER.error(
                "Unable to connect to the device %s: not exists", self._serial_port
            )
            self._attr_available = False
            return False

        try:
            # Create the connection instance.
            connection = serial.Serial(
                port=self._serial_port,
                baudrate=2400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
        except serial.SerialException as exec:
            _LOGGER.exception(
                "Unable to connect to the device %s: %s", self._serial_port, exec
            )
            return False
        _LOGGER.debug("Device %s connected", self._serial_port)

        try:
            # Open the connection.
            if not connection.is_open:
                connection.open()

            # Send the command.
            connection.write(COMMAND_DICT[command])
            connection.flush()
            _LOGGER.info("Command successfully send")

            # Close the connection.
            connection.close()

            return True
        except serial.SerialException as exec:
            _LOGGER.exception(
                "Error while writing device %s: %s", self._serial_port, exec
            )

        return False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._send_command(CONF_COMMAND_OPEN):
            self._direction = CONF_COMMAND_OPEN
            self._timestamp = time.time() - (self._percentage * (self._time_open / 100))
            self.start_updater()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._send_command(CONF_COMMAND_CLOSE):
            self._direction = CONF_COMMAND_CLOSE
            self._timestamp = time.time() - (
                (100.0 - self._percentage) * (self._time_close / 100)
            )
            self.start_updater()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._send_command(CONF_COMMAND_STOP):
            self._direction = CONF_COMMAND_STOP
            self.stop_updater()
