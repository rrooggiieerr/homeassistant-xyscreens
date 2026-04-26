"""The XY Screens integration."""

import asyncio
import logging
from pathlib import Path
from typing import Any

import serial
import serial_asyncio_fast as serial_asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ADDRESS,
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_NETWORK,
    CONF_CONNECTION_TYPE_SERIAL,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
    CONF_HOST,
    CONF_INVERTED,
    CONF_PORT,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
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


async def test_tcp_connection(host: str, port: int):
    """Test the working of a TCP connection."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5.0
        )
        writer.close()
        await writer.wait_closed()
        _LOGGER.debug("TCP connection to %s:%d is available", host, port)
    except (asyncio.TimeoutError, OSError, ConnectionError) as ex:
        _LOGGER.error("Failed to connect to %s:%d: %s", host, port, ex)
        raise


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up XY Screens from a config entry."""
    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)

    # Get connection type (default to serial for backward compatibility)
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONF_CONNECTION_TYPE_SERIAL)

    if connection_type == CONF_CONNECTION_TYPE_SERIAL:
        # Test serial connection
        serial_port = entry.data[CONF_SERIAL_PORT]
        if not Path(serial_port).exists():
            raise ConfigEntryNotReady(f"Device {serial_port} does not exist")

        try:
            await test_serial_port(serial_port)
        except serial.SerialException as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to device {serial_port}: {ex}"
            ) from ex

    elif connection_type == CONF_CONNECTION_TYPE_NETWORK:
        # Test network connection
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]

        try:
            await test_tcp_connection(host, int(port))
        except Exception as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to {host}:{port}: {ex}"
            ) from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # It should not be necessary to close the serial port because we close
    # it after every use in cover.py, i.e. no need to do entry["client"].close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version > 3:
        # This means the user has downgraded from a future version
        return False

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
        if config_entry.minor_version < 2:
            _LOGGER.debug("Migrating config entry from 2.1 to 2.2")
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
            minor_version=2,
            version=2,
        )

    if config_entry.version == 3:
        hass.config_entries.async_update_entry(
            config_entry,
            minor_version=2,
            version=2,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


@callback
def async_migrate_entity_entry(
    entry: er.RegistryEntry,
) -> dict[str, Any] | None:
    """Migrates old unique ID to the new unique ID."""
    if entry.unique_id != entry.config_entry_id:
        _LOGGER.debug("Migrating entity unique id")
        return {"new_unique_id": entry.config_entry_id}

    # No migration needed
    return None
