"""Constants for the XY Screens integration."""
from homeassistant.const import CONF_COMMAND_CLOSE, CONF_COMMAND_OPEN, CONF_COMMAND_STOP

DOMAIN = "xyscreens"

CONF_SERIAL_PORT = "serial_port"
CONF_TIME_OPEN = "time_open"
CONF_TIME_CLOSE = "time_close"
CONF_MANUAL_PATH = "manual_path"

COMMAND_DICT = {
    CONF_COMMAND_OPEN: bytearray.fromhex("FFAAEEEEDD"),
    CONF_COMMAND_CLOSE: bytearray.fromhex("FFAAEEEEEE"),
    CONF_COMMAND_STOP: bytearray.fromhex("FFAAEEEECC"),
}
