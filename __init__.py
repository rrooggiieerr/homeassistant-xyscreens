"""The XY Screens integration."""
import logging
import os

import serial

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XY Screens from a config entry."""

    # Test if the device exists.
    serial_port = entry.data[CONF_SERIAL_PORT]
    if not os.path.exists(serial_port):
        raise ConfigEntryNotReady(
            f"Device {serial_port} does not exists"
        )

    # Test if we can connect to the device.
    try:
        # Create the connection instance.
        connection = serial.Serial(
            port=serial_port,
            baudrate=2400,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        )

        # Open the connection.
        if not connection.is_open:
            connection.open()

        # Close the connection.
        connection.close()

        _LOGGER.info("Device %s is available", serial_port)
    except serial.SerialException as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to device {serial_port}: {ex}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # It should not be necessary to close the serial port because we close
    # it after every use in cover.py, i.e. no need to do entry["client"].close()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
