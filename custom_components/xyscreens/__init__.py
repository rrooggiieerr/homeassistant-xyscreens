"""The XY Screens integration."""

import logging
import os

import serial
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL_PORT, CONF_TIME_CLOSE, CONF_TIME_OPEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def test_serial_port(hass: HomeAssistant, serial_port):
    """Test the working of a serial port."""

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
        await hass.async_add_executor_job(connection.open)

    # Close the connection.
    await hass.async_add_executor_job(connection.close)

    _LOGGER.info("Device %s is available", serial_port)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XY Screens from a config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Test if the device exists.
    serial_port = entry.data[CONF_SERIAL_PORT]
    if not os.path.exists(serial_port):
        raise ConfigEntryNotReady(f"Device {serial_port} does not exists")

    # Test if we can connect to the device.
    try:
        await test_serial_port(hass, serial_port)
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


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry from 1 to 2")
        new_title = config_entry.data.get(CONF_SERIAL_PORT)

        new_data = {CONF_SERIAL_PORT: config_entry.data.get(CONF_SERIAL_PORT)}

        new_options = {
            CONF_TIME_OPEN: config_entry.data.get(CONF_TIME_OPEN),
            CONF_TIME_CLOSE: config_entry.data.get(CONF_TIME_CLOSE),
        }

        config_entry.version = 2
        hass.config_entries.async_update_entry(
            config_entry, title=new_title, data=new_data, options=new_options
        )

    return True
