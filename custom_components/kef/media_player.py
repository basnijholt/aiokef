"""Platform for the KEF Wireless Speakers."""

import asyncio
import functools
import logging
import time
from enum import Enum

import voluptuous as vol
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    MediaPlayerDevice,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.helpers import config_validation as cv

from custom_components.kef.async_kef_api import INPUT_SOURCES, AsyncKefSpeaker

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "KEF"
DEFAULT_PORT = 50001
DEFAULT_MAX_VOLUME = 0.5
DEFAULT_VOLUME_STEP = 0.05
DATA_KEF = "kef"

UPDATE_TIMEOUT = 1.0  # Timeout when a new source is selected.
BOOTING_ON_OFF_TIMEOUT = 20.0  # Timeout when turning speaker on or off.
# When changing volume or source, wait for the speaker until it is online for:
WAIT_FOR_ONLINE_STATE = 10.0

SCAN_INTERVAL = 15  # Used in HA.

KEF_LS50_SOURCES = sorted(INPUT_SOURCES.keys())

SUPPORT_KEF = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

CONF_MAX_VOLUME = "maximum_volume"
CONF_VOLUME_STEP = "volume_step"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): cv.small_float,
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): cv.small_float,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup Kef platform."""
    if DATA_KEF not in hass.data:
        hass.data[DATA_KEF] = {}

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    maximum_volume = config.get(CONF_MAX_VOLUME)
    volume_step = config.get(CONF_VOLUME_STEP)

    _LOGGER.debug(
        f"Setting up {DATA_KEF} with host: {host}, port: {port},"
        f" name: {name}, sources: {KEF_LS50_SOURCES}"
    )

    media_player = KefMediaPlayer(
        name,
        host,
        port,
        maximum_volume=maximum_volume,
        volume_step=volume_step,
        sources=KEF_LS50_SOURCES,
        hass=hass,
    )
    unique_id = f"{host}:{port}"
    if unique_id in hass.data[DATA_KEF]:
        _LOGGER.debug(f"{unique_id} is already configured.")
    else:
        hass.data[DATA_KEF][unique_id] = media_player
        async_add_entities([media_player], True)


class States(Enum):
    Online = 1
    Offline = 2
    TurningOn = 3
    TurningOff = 4

    def is_changing(self):
        return self in (States.TurningOn, States.TurningOff)


def try_and_delay_update(delay):
    def deco(f):
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            try:
                self = args[0]
                await self._ensure_online()
                result = await f(*args, **kwargs)
                self._update_timeout = time.time() + delay
                return result
            except Exception as e:
                _LOGGER.warning(f"{f.__name__} failed with {e}")

        return wrapper

    return deco


class KefMediaPlayer(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(self, name, host, port, maximum_volume, volume_step, sources, hass):
        """Initialize the media player."""
        self._name = name
        self._hass = hass
        self._sources = sources
        self._speaker = AsyncKefSpeaker(
            host, port, volume_step, maximum_volume, ioloop=self._hass.loop
        )

        # Set internal states to None.
        self._state = None
        self._muted = None
        self._source = None
        self._volume = None
        self._update_timeout = time.time() - BOOTING_ON_OFF_TIMEOUT

    async def _ensure_online(self):
        """Use this function to wait for online state."""
        time_end = time.time() + WAIT_FOR_ONLINE_STATE
        while self._state is not States.Online and time.time() > time_end:
            await asyncio.sleep(0.1)
            if self._state is States.TurningOn:
                time_end = time.time() + WAIT_FOR_ONLINE_STATE

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if isinstance(self._state, States):
            return STATE_ON if self._state is States.Online else STATE_OFF
        else:
            return None

    async def async_update(self):
        """Update latest state."""
        updated_needed = time.time() >= self._update_timeout
        if self._state is not None and self._state.is_changing():
            # The speaker is turning on or off.
            if updated_needed:
                # Invalidate the state if it's time to update.
                self._state = None
            updated_needed = True

        try:
            is_online = await self._speaker.is_online()
            if is_online and self._state is not States.TurningOff:
                if updated_needed:
                    self._muted = await self._speaker.is_muted()
                    self._source = await self._speaker.get_source()
                    self._volume = await self._speaker.get_volume()
                self._state = States.Online
            elif not self._state.is_changing():
                # Speaker is not online and not turning on.
                self._muted = None
                self._source = None
                self._volume = None
                self._state = States.Offline
        except Exception as e:
            _LOGGER.debug(f"Error in `update`: {e}")

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_KEF

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources

    @try_and_delay_update(delay=BOOTING_ON_OFF_TIMEOUT)
    async def turn_off(self):
        """Turn the media player off."""
        await self._speaker.turn_off()
        self._state = States.TurningOff

    @try_and_delay_update(delay=BOOTING_ON_OFF_TIMEOUT)
    async def turn_on(self):
        """Turn the media player on."""
        source = None  # XXX: implement that it uses the latest used source
        await self._speaker.turn_on(source)
        self._state = States.TurningOn

    @try_and_delay_update(delay=0)
    async def volume_up(self):
        """Volume up the media player."""
        self._volume = await self._speaker.increase_volume()

    @try_and_delay_update(delay=0)
    async def volume_down(self):
        """Volume down the media player."""
        self._volume = await self._speaker.decrease_volume()

    @try_and_delay_update(delay=0)
    async def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._speaker.set_volume(volume)
        self._volume = volume

    @try_and_delay_update(delay=0)
    async def mute_volume(self, mute):
        """Mute (True) or unmute (False) media player."""
        if mute:
            await self._speaker.mute()
        else:
            await self._speaker.unmute()
        self._muted = mute

    @try_and_delay_update(delay=UPDATE_TIMEOUT)
    async def select_source(self, source: str):
        """Select input source."""
        if source in self.source_list:
            self._source = source
            await self._speaker.set_source(source)
        else:
            raise ValueError(f"Unknown input source: {source}.")
