#! /usr/bin/env python
"""pykef is the library for interfacing with KEF speakers"""

import asyncio
import contextlib
import logging
import select
import socket
from enum import Enum
from time import sleep, time

_LOGGER = logging.getLogger(__name__)
_VOL_STEP = 0.05  # 5% steps
_RESPONSE_OK = 17
_TIMEOUT = 1.0  # in seconds
_KEEP_ALIVE = 1.0  # in seconds
_SCALE = 100.0
_RETRIES = 10


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


class KefSpeaker:
    def __init__(self, host, port, *, ioloop=None):
        self._socket = None
        self._connected = False
        self._online = False
        self._last_timestamp = 0
        self._host = host
        self._port = int(port)
        self._ioloop = ioloop or asyncio.get_event_loop()
        self._disconnect_task = self._ioloop.create_task(self._disconnect_if_passive())

    def _refresh_connection(self):
        """Connect if not connected.

        Retry at max for 100 times, with longer interval each time.
        Update timestamp that keep connection alive.

        If unable to connect due to no route to host, set to offline

        If speaker is offline, max retires is infinite.
        """

        def setup_connection():
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(_TIMEOUT)
            return self._socket

        self._last_timestamp = time()

        if self._connected:
            return

        self._socket = setup_connection()
        self._connected = False
        wait = 0.1
        retries = 0
        while retries < _RETRIES:
            self._last_timestamp = time()
            try:
                self._socket.connect((self._host, self._port))
                self._connected = True
                self._online = True
                _LOGGER.debug("Online")
                _LOGGER.debug("Connected")
                break
            except ConnectionRefusedError:
                self._socket = setup_connection()
                wait += 0.1
                sleep(wait)
            except BlockingIOError:  # Connection ingoing
                retries = 0
                wait = _TIMEOUT
                sleep(wait)
            except OSError as e:  # Host is down
                self._online = False
                _LOGGER.debug("Offline")
                raise ConnectionRefusedError("Speaker is offline") from e
            except socket.timeout as e:  # Host went offline (probably)
                self._online = False
                _LOGGER.debug("Offline")
                raise ConnectionRefusedError("Speaker is offline") from e
            retries += 1

    async def _disconnect_if_passive(self):
        """Disconnect if connection is not used for a while (old timestamp)."""
        while True:
            should_disconnect = time() - self._last_timestamp > _KEEP_ALIVE
            if self._connected and should_disconnect:
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

    def _get_volume(self):
        _LOGGER.debug("_get_volume()")
        msg = bytes([0x47, 0x25, 0x80, 0x6C])
        return self._send_command(msg)

    def _set_volume(self, volume):
        _LOGGER.debug(f"_set_volume({volume}")
        # write vol level in 4th place, add 128 to current level to mute
        msg = bytes([0x53, 0x25, 0x81, int(volume), 0x1A])
        return self._send_command(msg) == _RESPONSE_OK

    def _get_source(self):
        _LOGGER.debug("_get_source()")
        msg = bytes([0x47, 0x30, 0x80, 0xD9])
        table = {
            18: InputSource.Wifi,
            25: InputSource.Bluetooth,
            26: InputSource.Aux,
            27: InputSource.Opt,
            28: InputSource.Usb,
            31: InputSource.Bluetooth,
        }
        response = self._send_command(msg)

        return table.get(response)

    def _set_source(self, source):
        _LOGGER.debug(f"_set_source({source})")
        return self._send_command(source.value) == _RESPONSE_OK

    @property
    def volume(self):
        """Volume level of the media player (0..1). None if muted"""
        volume = self._get_volume()

        # _get_volume/_sendcommand might return None due too network errors
        if volume is not None:
            return volume / _SCALE if volume < 128 else None
        else:
            return None

    @volume.setter
    def volume(self, value):
        if value:
            volume = int(max(0.0, min(1.0, value)) * _SCALE)
        else:
            current_volume = self._get_volume()
            if current_volume:
                volume = int(current_volume) % 128 + 128
        self._set_volume(volume)

    @property
    def source(self):
        """Get the input source of the speaker."""
        return self._get_source()

    @source.setter
    def source(self, value):
        self._set_source(value)

    @property
    def muted(self):
        return self._get_volume() > 128

    @muted.setter
    def muted(self, value):
        current_volume = self._get_volume()
        if current_volume is None:
            return
        self._set_volume(int(current_volume) % 128 + 128 * int(bool(value)))

    @property
    def online(self):
        with contextlib.suppress(Exception):
            self._refresh_connection()
        return self._online

    def turn_on(self, source=None):
        """The speaker can be turned on by selecting an InputSource."""
        if source is None:
            source = InputSource.Wifi
        return self._set_source(source)

    def turn_off(self):
        msg = bytes([0x53, 0x30, 0x81, 0x9B, 0x0B])
        return self._send_command(msg) == _RESPONSE_OK

    def increase_volume(self, step=None):
        """Increase volume by step, or 5% by default.

        Constrait: 0.0 < step < 1.0.
        """
        volume = self.volume
        if volume:
            step = step or _VOL_STEP
            self.volume = volume + step

    def decrease_volume(self, step=None):
        """Decrease volume by step, or 5% by default.

        Constrait: 0.0 < step < 1.0.
        """
        self.increase_volume(-(step or _VOL_STEP))
