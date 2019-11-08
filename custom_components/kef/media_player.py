"""Platform for the KEF Wireless Speakers."""

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

from custom_components.kef.pykef import InputSource, KefSpeaker

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

KEF_LS50_SOURCE_DICT = {str(i + 1): str(s) for i, s in enumerate(InputSource)}

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


def setup_platform(hass, config, add_entities, discovery_info=None):
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
        " name: {name}, source_dict: {KEF_LS50_SOURCE_DICT}"
    )

    media_player = KefMediaPlayer(
        name,
        host,
        port,
        maximum_volume=maximum_volume,
        volume_step=volume_step,
        source_dict=KEF_LS50_SOURCE_DICT,
        hass=hass,
    )
    unique_id = f"{host}:{port}"
    if unique_id in hass.data[DATA_KEF]:
        _LOGGER.debug(f"{unique_id} is already configured.")
    else:
        hass.data[DATA_KEF][unique_id] = media_player
        add_entities([media_player])


class States(Enum):
    Online = 1
    Offline = 2
    TurningOn = 3
    TurningOff = 4


def try_this(wait=False):
    def try_dis(f):
        def wrapper(*args, **kwargs):
            if wait:
                self = args[0]
                self._ensure_online()
            try:
                return f(*args, **kwargs)
            except Exception as e:
                _LOGGER.debug(f"{f.__name__} failed with {e}")
        return wrapper
    return try_dis


class KefMediaPlayer(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(
        self, name, host, port, maximum_volume, volume_step, source_dict, hass
    ):
        """Initialize the media player."""
        self._name = name
        self._hass = hass
        self._source_dict = source_dict
        self._speaker = KefSpeaker(
            host, port, volume_step, maximum_volume, ioloop=self._hass.loop
        )

        # Set internal states to None.
        self._state = None
        self._mute = None
        self._source = None
        self._volume = None
        self._update_timeout = time.time() - BOOTING_ON_OFF_TIMEOUT

    def _internal_state(self):
        """Return text with the internal states, just for debugging."""
        return (
            f"self._state={self._state}, self._mute={self._mute},"
            " self._source={self._source}, self._volume={self._volume}"
        )

    def _ensure_online(self):
        """Use this function to wait for online state."""
        time_to_wait = WAIT_FOR_ONLINE_STATE
        while time_to_wait > 0:
            time_to_sleep = 0.1
            time_to_wait -= time_to_sleep
            time.sleep(time_to_sleep)
            if self._state is States.TurningOn:
                time_to_wait = 10
            if self._state is States.Online:
                return

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

    def update(self):
        """Update latest state."""
        updated_needed = time.time() >= self._update_timeout
        if self._state in [States.TurningOn, States.TurningOff]:
            if updated_needed:
                self._state = States.Offline
            updated_needed = True
        try:
            is_online = self._speaker.online
            if is_online and self._state in [
                States.Online,
                States.Offline,
                States.TurningOn,
                None,
            ]:
                if updated_needed:
                    self._mute = self._speaker.muted
                    self._source = str(self._speaker.source)
                    self._volume = self._speaker.volume
                self._state = States.Online
            elif self._state in [States.Online, States.Offline, None]:
                self._mute = None
                self._source = None
                self._volume = None
                self._state = States.Offline
        except Exception as e:
            _LOGGER.debug("Update: " + self._internal_state())
            _LOGGER.debug(e)

        _LOGGER.debug("Update: " + self._internal_state())

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Flag media player features that are supported.
        """
        return SUPPORT_KEF

    @try_this(wait=False)
    def turn_off(self):
        """Turn the media player off."""
        response = self._speaker.turn_off()
        if response:
            self._state = States.TurningOff
            self._update_timeout = time.time() + BOOTING_ON_OFF_TIMEOUT

    @try_this()
    def turn_on(self):
        """Turn the media player on."""
        source = None  # XXX: implement that it uses the latest used source
        response = self._speaker.turn_on(source)
        if response:
            self._state = States.TurningOn
            self._update_timeout = time.time() + BOOTING_ON_OFF_TIMEOUT

    @try_this()
    def volume_up(self):
        """Volume up the media player."""
        self._volume = self._speaker.increase_volume()
        self._update_timeout = time.time() + UPDATE_TIMEOUT

    @try_this()
    def volume_down(self):
        """Volume down the media player."""
        self._volume = self._speaker.decrease_volume()
        self._update_timeout = time.time() + UPDATE_TIMEOUT

    @try_this()
    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._speaker.volume = volume
        self._volume = volume
        self._update_timeout = time.time() + UPDATE_TIMEOUT

    @try_this()
    def select_source(self, source):
        """Select input source."""
        if source in self.source_list:
            self._source = str(source)
            self._speaker.source = input_source
            self._update_timeout = time.time() + UPDATE_TIMEOUT
        else:
            _LOGGER.warning(f"select_source: unknown input {source}")

    @property
    def source(self):
        """Name of the current input source."""
        _LOGGER.debug(f"source - returning {self._source}")
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        _LOGGER.debug("source_list")
        return sorted(list(self._source_dict.values()))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        try:
            self._speaker.muted = mute
            self._mute = mute
            self._update_timeout = time.time() + UPDATE_TIMEOUT
        except Exception:
            _LOGGER.warning("mute_volume: failed")
