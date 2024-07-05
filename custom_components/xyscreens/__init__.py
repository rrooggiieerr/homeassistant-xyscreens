"""The XY Screens integration."""

import logging
import os

import serial
import serial_asyncio_fast as serial_asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
    CONF_INVERTED,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def test_serial_port(serial_port):
    """Test the working of a serial port."""

    # Create the connection instance.
    _, writer = await serial_asyncio.open_serial_connection(
        url=serial_port,
        baudrate=2400,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1,
    )

    # Close the connection.
    writer.close()
    await writer.wait_closed()

    _LOGGER.debug("Device %s is available", serial_port)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XY Screens from a config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Test if the device exists.
    serial_port = entry.data[CONF_SERIAL_PORT]
    if not os.path.exists(serial_port):
        raise ConfigEntryNotReady(f"Device {serial_port} does not exists")

    # Test if we can connect to the device.
    try:
        await test_serial_port(serial_port)
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

        hass.config_entries.async_update_entry(
            config_entry, title=new_title, data=new_data, options=new_options, version=2
        )

    if config_entry.version == 2:
        _LOGGER.debug("Migrating config entry from 2 to 3")
        new_unique_id = f"{config_entry.data.get(CONF_SERIAL_PORT)}-aaeeee"
        new_title = f"{config_entry.data.get(CONF_SERIAL_PORT)} AAEEEE"
        new_data = {
            CONF_SERIAL_PORT: config_entry.data.get(CONF_SERIAL_PORT),
            CONF_ADDRESS: "aaeeee",
            CONF_DEVICE_TYPE: CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
        }
        new_options = {
            CONF_TIME_OPEN: config_entry.options.get(CONF_TIME_OPEN),
            CONF_TIME_CLOSE: config_entry.options.get(CONF_TIME_CLOSE),
            CONF_INVERTED: config_entry.options.get(CONF_INVERTED, False),
        }

        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=new_unique_id,
            title=new_title,
            data=new_data,
            options=new_options,
            version=3,
        )

    return True
