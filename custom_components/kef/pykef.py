"""A module for interacting with KEF wireless speakers."""

import asyncio
import contextlib
import functools
import logging
import select
import socket
import time
from enum import Enum

_LOGGER = logging.getLogger(__name__)
_RESPONSE_OK = 17
_TIMEOUT = 1.0  # in seconds
_KEEP_ALIVE = 1.0  # in seconds
_SCALE = 100.0
_MAX_RETRIES = 10


class InputSource(Enum):
    Wifi = bytes([0x53, 0x30, 0x81, 0x12, 0x82])
    Bluetooth = bytes([0x53, 0x30, 0x81, 0x19, 0xAD])
    Aux = bytes([0x53, 0x30, 0x81, 0x1A, 0x9B])
    Opt = bytes([0x53, 0x30, 0x81, 0x1B, 0x00])
    Usb = bytes([0x53, 0x30, 0x81, 0x1C, 0xF7])

    def __str__(self):
        return {s: s.name for s in InputSource}[self]

    @classmethod
    def from_str(cls, name):
        try:
            return next(s for s in InputSource if s.name == name)
        except StopIteration:
            return None


def retry(ExceptionToCheck, tries=4, delay=0.1, backoff=2):
    """Retry calling the decorated function using an exponential backoff.

    Parameters
    ----------
    ExceptionToCheck : Exception or tuple
        The exception to check. May be a tuple of exceptions to check.
    tries :  int
        Number of times to try (not retry) before giving up.
    delay : int
        Initial delay between tries in seconds.
    backoff : int
        Backoff multiplier e.g. value of 2 will double the delay each retry.
    """

    def deco_retry(f):
        @functools.wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    _LOGGER.debug(f"{e}, Retrying {f.__name__} in {mdelay} seconds...")
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


class KefSpeaker:
    def __init__(
        self, host, port, volume_step=0.05, maximum_volume=1.0, *, ioloop=None
    ):
        self._socket = None
        self._connected = False
        self._online = False
        self._last_timestamp = 0
        self.host = host
        self.port = int(port)
        self._ioloop = ioloop or asyncio.get_event_loop()
        self._disconnect_task = self._ioloop.create_task(self._disconnect_if_passive())
        self.volume_step = volume_step
        self.maximum_volume = maximum_volume

    def _refresh_connection(self):
        """Connect if not connected.

        Retry at max for 100 times, with longer interval each time.
        Update timestamp that keep connection alive.

        If unable to connect due to no route to host, set to offline.

        If speaker is offline, max retries is infinite.
        """

        def setup_connection():
            if self._socket is not None:
                # Close the previous socket.
                # XXX: is this needed?
                self._socket.close()
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(_TIMEOUT)
            return self._socket

        self._last_timestamp = time.time()

        if self._connected:
            return

        self._socket = setup_connection()
        self._connected = False
        wait = 0.1
        retries = 0
        while retries < _MAX_RETRIES:
            self._last_timestamp = time.time()
            try:
                self._socket.connect((self.host, self.port))
                self._connected = True
                self._online = True
            except ConnectionRefusedError:
                self._socket = setup_connection()
                wait += 0.1
                time.sleep(wait)
            except BlockingIOError:  # Connection incomming
                retries = 0
                wait = _TIMEOUT
                time.sleep(wait)
            except (OSError, socket.timeout) as e:  # Host is down
                self._online = False
                _LOGGER.debug("Offline")
                raise ConnectionRefusedError("Speaker is offline") from e
            else:
                _LOGGER.debug("Online")
                _LOGGER.debug("Connected")
                return
            retries += 1

    async def _disconnect_if_passive(self):
        """Disconnect if connection is not used for _KEEP_ALIVE seconds."""
        while True:
            time_is_up = time.time() - self._last_timestamp > _KEEP_ALIVE
            if self._connected and time_is_up:
                self._connected = False
                self._socket.close()
                _LOGGER.debug("Disconneced")
            await asyncio.sleep(0.1)

    def _send_command(self, message):
        """Send command to speakers, returns the response."""
        self._refresh_connection()
        if self._connected:
            self._socket.sendall(message)
            self._socket.setblocking(0)
            ready = select.select([self._socket], [], [], _TIMEOUT)
            data = self._socket.recv(1024) if ready[0] else None
            self._socket.setblocking(1)
        else:
            raise OSError("_send_command failed")
        return data[len(data) - 2] if data else None

    @retry(ConnectionError, tries=5)
    def get_source(self):
        _LOGGER.debug("_get_source()")
        msg = bytes([0x47, 0x30, 0x80, 0xD9])
        response = self._send_command(msg)
        table = {
            18: InputSource.Wifi,
            25: InputSource.Bluetooth,
            26: InputSource.Aux,
            27: InputSource.Opt,
            28: InputSource.Usb,
            31: InputSource.Bluetooth,
        }
        source = table.get(response)
        if source is None:
            raise ConnectionError("Getting source failed.")
        return source

    @retry(ConnectionError, tries=5)
    def set_source(self, source):
        _LOGGER.debug(f"set_source({source})")
        if isinstance(source, str):
            source = InputSource.from_str(source)
        assert isinstance(source, InputSource)
        if self._send_command(source.value) != _RESPONSE_OK:
            raise ConnectionError("Setting source failed.")

    @retry(ConnectionError, tries=5)
    def _get_volume(self, scale=True):
        _LOGGER.debug(f"_get_volume(scale={scale})")
        msg = bytes([0x47, 0x25, 0x80, 0x6C])
        volume = self._send_command(msg)
        if volume is None:
            raise ConnectionError("Getting volume failed.")
        return volume / _SCALE if scale else volume

    @retry(ConnectionError, tries=5)
    def _set_volume(self, volume: int):
        _LOGGER.debug(f"_set_volume(volume={volume}")
        # write vol level in 4th place, add 128 to current level to mute
        msg = bytes([0x53, 0x25, 0x81, int(volume), 0x1A])
        if self._send_command(msg) != _RESPONSE_OK:
            raise ConnectionError("Setting the volume failed.")

    def get_volume(self):
        """Volume level of the media player (0..1). None if muted."""
        volume = self._get_volume(scale=True)
        return volume if not self.is_muted() else None

    def set_volume(self, value: float):
        volume = int(max(0.0, min(self.maximum_volume, value)) * _SCALE)
        self._set_volume(volume)

    def _change_volume(self, step: float):
        """Change volume by `step`."""
        volume = self.get_volume()
        if not self.is_muted():
            new_volume = volume + step
            self.set_volume(new_volume)
            return new_volume

    def increase_volume(self) -> float:
        """Increase volume by `self.volume_step`."""
        return self._change_volume(self.volume_step)

    def decrease_volume(self) -> float:
        """Decrease volume by `self.volume_step`."""
        return self._change_volume(-self.volume_step)

    def is_muted(self):
        return self._get_volume(scale=False) > 128

    def mute(self):
        volume = self._get_volume(scale=False)
        self._set_volume(int(volume) % 128 + 128)

    def unmute(self):
        volume = self._get_volume(scale=False)
        self._set_volume(int(volume) % 128)

    @property
    def online(self):
        # This is a property because `_refresh_connection` is very fast, ~5 ms.
        with contextlib.suppress(Exception):
            self._refresh_connection()
        return self._online

    def turn_on(self, source=None):
        """The speaker can be turned on by selecting an InputSource."""
        # XXX: it might be possible to turn on the speaker with the last
        # used source selected.
        if source is None:
            source = InputSource.Wifi
        self.set_source(source)

    @retry(ConnectionError, tries=5)
    def turn_off(self):
        msg = bytes([0x53, 0x30, 0x81, 0x9B, 0x0B])
        if self._send_command(msg) != _RESPONSE_OK:
            raise ConnectionError("Turning off failed.")
