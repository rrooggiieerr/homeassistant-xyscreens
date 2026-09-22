"""The XY Screens cover entity."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import functools
import logging
from typing import Any, Final, override

from xyscreens import XYScreens, XYScreensConnectionError, XYScreensState

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_ADDRESS_XYSCREENS,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_TYPE_PROJECTOR_SCREEN,
    CONF_INVERTED,
    CONF_SERIAL_PORT,
    CONF_TIME_CLOSE,
    CONF_TIME_OPEN,
    DOMAIN,
)

_LOGGER: Final = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the XY Screens cover."""
    open_time = config_entry.options[CONF_TIME_OPEN]
    async_add_entities(
        [
            XYScreensCover(
                config_entry.entry_id,
                config_entry.data[CONF_SERIAL_PORT],
                bytes.fromhex(
                    config_entry.data.get(CONF_ADDRESS, CONF_ADDRESS_XYSCREENS)
                ),
                config_entry.data.get(
                    CONF_DEVICE_TYPE, CONF_DEVICE_TYPE_PROJECTOR_SCREEN
                ),
                open_time,
                config_entry.options.get(CONF_TIME_CLOSE, open_time),
                config_entry.options.get(CONF_INVERTED, False),
            )
        ]
    )


def _xyscreens_error_wrapper[T](
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> T:
        try:
            return await func(self, *args, **kwargs)
        except XYScreensConnectionError as exc:
            self._attr_available = False
            self.async_write_ha_state()
            self._start_updater()

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from exc

    return wrapper


class XYScreensCover(CoverEntity, RestoreEntity):
    """The XY Screens cover."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_should_poll = False

    _attr_is_closed = False

    _unsubscribe_updater = None
    _update_interval = None

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry_id)},
            translation_key=device_type,
            manufacturer="XY Screens",
        )
        self._attr_unique_id = config_entry_id

        self._entry_id = config_entry_id

        translation_key = f"{device_type}_inverted" if inverted else device_type

        self.entity_description = CoverEntityDescription(
            key=device_type,
            has_entity_name=True,
            translation_key=translation_key,
            name=None,  # Inherit the device name
        )

        self._screen = XYScreens(serial_port, address, time_open, time_close)

        self._inverted = inverted

    @override
    async def async_added_to_hass(self) -> None:
        """Called when cover is added to Home Assistant."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            position = last_state.attributes[ATTR_CURRENT_POSITION]
            _LOGGER.debug("Last screen position: %5.1f %%", position)
            if not self._inverted:
                self._screen.restore_position(100 - position)
            else:
                self._screen.restore_position(position)
            self._attr_current_cover_position = position
            if position == 0:
                self._attr_is_closed = True

    async def async_update(self) -> None:
        """Update Home Assistant with current state of entity."""
        if not self._attr_available and not await self._screen.async_test_connection():
            return

        self._attr_available = True

        state, position = self._screen.update_status()

        if not self._inverted:
            position = 100 - position
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

    def _start_updater(self, interval=SCAN_INTERVAL):
        """Start the updater to update Home Assistant while projector screen/lift is moving."""
        if self._unsubscribe_updater and self._update_interval != interval:
            self._stop_updater()

        if self._unsubscribe_updater is None:
            self._update_interval = interval
            self._unsubscribe_updater = async_track_time_interval(
                self.hass, self._updater_hook, interval
            )

    @callback
    def _updater_hook(self, now):
        """Call for the updater."""
        self.async_schedule_update_ha_state(True)

    def _stop_updater(self):
        """Stop the updater."""
        if self._unsubscribe_updater is not None:
            self._unsubscribe_updater()
            self._unsubscribe_updater = None
            self._update_interval = None

    @_xyscreens_error_wrapper
    async def _async_open_cover(self, **kwargs: Any) -> None:
        await self._screen.async_up()
        self._start_updater(timedelta(seconds=1))

    @_xyscreens_error_wrapper
    async def _async_close_cover(self, **kwargs: Any) -> None:
        await self._screen.async_down()
        self._start_updater(timedelta(seconds=1))

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if not self._inverted:
            await self._async_open_cover()
        else:
            await self._async_close_cover()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if not self._inverted:
            await self._async_close_cover()
        else:
            await self._async_open_cover()

    @override
    @_xyscreens_error_wrapper
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._screen.async_stop()
        self._stop_updater()
        self.async_schedule_update_ha_state(True)

    @override
    @_xyscreens_error_wrapper
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self.current_cover_position == position:
            return

        if not self._inverted:
            await self._screen.async_set_position(100 - position)
        else:
            await self._screen.async_set_position(position)

        self._start_updater(timedelta(seconds=1))
