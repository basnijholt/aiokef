"""A module for asynchronously interacting with KEF wireless speakers."""

import asyncio
import functools
import inspect
import logging
import socket
import sys
import time

from tenacity import retry, stop_after_attempt, wait_exponential, before_log

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

_LOGGER = logging.getLogger(__name__)
_RESPONSE_OK = 17
_TIMEOUT = 2.0  # in seconds
_KEEP_ALIVE = 10  # in seconds
_VOLUME_SCALE = 100.0
_MAX_SEND_COMMAND_TRIES = 5  # XXX: not used ATM
_MAX_CONNECTION_RETRIES = 10  # Each time `_send_command` is called, ...
# ... the connection is maximally refreshed this many times.


INPUT_SOURCES = {
    "Wifi": dict(msg=bytes([0x53, 0x30, 0x81, 0x12, 0x82]), response=18),
    "Bluetooth": dict(msg=bytes([0x53, 0x30, 0x81, 0x19, 0xAD]), response=31),
    "Aux": dict(msg=bytes([0x53, 0x30, 0x81, 0x1A, 0x9B]), response=26),
    "Opt": dict(msg=bytes([0x53, 0x30, 0x81, 0x1B, 0x00]), response=27),
    "Usb": dict(msg=bytes([0x53, 0x30, 0x81, 0x1C, 0xF7]), response=28),
}

INPUT_SOURCES_RESPONSE = {v["response"]: k for k, v in INPUT_SOURCES.items()}

COMMANDS = {
    "turn_off": bytes([0x53, 0x30, 0x81, 0x9B, 0x0B]),
    "get_source": bytes([0x47, 0x30, 0x80, 0xD9]),
    "get_volume": bytes([0x47, 0x25, 0x80, 0x6C]),
    "set_volume": lambda volume: bytes([0x53, 0x25, 0x81, int(volume), 0x1A]),
}


class _AsyncCommunicator:
    def __init__(self, host, port, *, ioloop=None):
        self.host = host
        self.port = port
        self._reader, self._writer = (None, None)
        self._last_time_stamp = 0
        self._is_online = False
        self._ioloop = ioloop or asyncio.get_event_loop()
        self._disconnect_task = self._ioloop.create_task(self._disconnect_if_passive())

    @property
    def is_connected(self):
        return (self._reader, self._writer) != (None, None)

    async def open_connection(self):
        if self.is_connected:
            _LOGGER.debug("Connection is still alive")
            return
        retries = 0
        while retries < _MAX_CONNECTION_RETRIES:
            _LOGGER.debug("Opening connection")
            try:
                task = asyncio.open_connection(
                    self.host, self.port, family=socket.AF_INET
                )
                self._reader, self._writer = await asyncio.wait_for(
                    task, timeout=_TIMEOUT
                )
            except ConnectionRefusedError:
                _LOGGER.debug("Opening connection failed")
                await asyncio.sleep(1)
            except BlockingIOError:  # Connection incomming
                # XXX: I have never seen this.
                retries = 0
                await asyncio.sleep(1)
            except (asyncio.TimeoutError, OSError) as e:  # Host is down
                self._is_online = False
                raise ConnectionRefusedError("Speaker is offline.") from e
            else:
                self._is_online = True
                self._last_time_stamp = time.time()
                return
            retries += 1
        self._is_online = False
        raise ConnectionRefusedError("Connection tries exceeded.")

    async def _send_message(self, message):
        _LOGGER.debug(f"Writing message: {message}")
        self._writer.write(message)
        await self._writer.drain()

        _LOGGER.debug("Reading message")
        read_task = self._reader.read(100)
        try:
            data = await asyncio.wait_for(read_task, timeout=_TIMEOUT)
            _LOGGER.debug(f"Got reply, {data}")
            self._last_time_stamp = time.time()
            return data[-2]
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout in waiting for reply")

    async def _disconnect(self):
        if self.is_connected:
            _LOGGER.debug("Disconnecting")
            self._writer.close()
            await self._writer.wait_closed()
            self._reader, self._writer = (None, None)

    async def _disconnect_if_passive(self):
        """Disconnect socket after _KEEP_ALIVE seconds of not using it."""
        while True:
            time_is_up = time.time() - self._last_time_stamp > _KEEP_ALIVE
            if self.is_connected and time_is_up:
                await self._disconnect()
            await asyncio.sleep(0.05)

    @retry(
        stop=stop_after_attempt(_MAX_SEND_COMMAND_TRIES),
        wait=wait_exponential(exp_base=1.5),
        before=before_log(_LOGGER, logging.DEBUG),
    )
    async def send_message(self, msg):
        await self.open_connection()
        reply = await self._send_message(msg)
        _LOGGER.debug(f"Received: {reply}")
        return reply


class AsyncKefSpeaker:
    """Asynchronous KEF speaker class.

    Parameters
    ----------
    host : str
        The IP of the speaker.
    port : int, optional
        The port used for the communication, the default is 50001.
    volume_step : float, optional
        The volume change when calling `increase_volume` or
        `decrease_volume`, by default 0.05.
    maximum_volume : float, optional
        The maximum allow volume, between 0 and 1. Use this to avoid
        accidentally setting very high volumes, by default 1.0.
    ioloop : `asyncio.BaseEventLoop`, optional
        The eventloop to use.

    Attributes
    ----------
    sync : SyncKefSpeaker
        Run any method that the `AsyncKefSpeaker` has in a synchronous way.
        For example ``kef_speaker.sync.mute()``.
    """
    def __init__(
        self, host, port=50001, volume_step=0.05, maximum_volume=1.0, *, ioloop=None
    ):
        self.host = host
        self.port = port
        self.volume_step = volume_step
        self.maximum_volume = maximum_volume
        self._comm = _AsyncCommunicator(host, port, ioloop=ioloop)
        self.sync = SyncKefSpeaker(self)

    async def get_source(self):
        response = await self._comm.send_message(COMMANDS["get_source"])
        source = INPUT_SOURCES_RESPONSE.get(response)
        if source is None:
            raise ConnectionError("Getting source failed, got response {response}.")
        return source

    async def set_source(self, source: str):
        assert source in INPUT_SOURCES
        response = await self._comm.send_message(INPUT_SOURCES[source]["msg"])
        if response != _RESPONSE_OK:
            raise ConnectionError("Setting source failed, got response {response}.")

    async def _get_volume(self, scale=True):
        volume = await self._comm.send_message(COMMANDS["get_volume"])
        if volume is None:
            raise ConnectionError("Getting volume failed.")
        return volume / _VOLUME_SCALE if scale else volume

    async def _set_volume(self, volume: int):
        # Write volume level (0..100) on index 3,
        # add 128 to current level to mute.
        response = await self._comm.send_message(COMMANDS["set_volume"](volume))
        if response != _RESPONSE_OK:
            raise ConnectionError(
                f"Setting the volume failed, got response {response}."
            )

    async def turn_off(self):
        response = await self._comm.send_message(COMMANDS["turn_off"])
        if response != _RESPONSE_OK:
            raise ConnectionError("Turning off failed, got response {response}.")

    async def get_volume(self) -> float:
        """Volume level of the media player (0..1). None if muted."""
        volume = await self._get_volume(scale=True)
        is_muted = await self.is_muted()
        return volume if not is_muted else None

    async def set_volume(self, value: float):
        volume = max(0.0, min(self.maximum_volume, value))
        await self._set_volume(int(volume * _VOLUME_SCALE))
        return volume

    async def _change_volume(self, step: float):
        """Change volume by `step`."""
        volume = await self.get_volume()
        is_muted = await self.is_muted()
        if not is_muted:
            return await self.set_volume(volume + step)

    async def increase_volume(self) -> float:
        """Increase volume by `self.volume_step`."""
        return await self._change_volume(self.volume_step)

    async def decrease_volume(self) -> float:
        """Decrease volume by `self.volume_step`."""
        return await self._change_volume(-self.volume_step)

    async def is_muted(self) -> bool:
        return await self._get_volume(scale=False) > 128

    async def mute(self):
        volume = await self._get_volume(scale=False)
        await self._set_volume(int(volume) % 128 + 128)

    async def unmute(self):
        volume = await self._get_volume(scale=False)
        await self._set_volume(int(volume) % 128)

    def is_online(self) -> bool:
        asyncio.run(self._comm.open_connection())
        return self._comm._is_online

    async def turn_on(self, source=None):
        """The speaker can be turned on by selecting an INPUT_SOURCE."""
        # XXX: it might be possible to turn on the speaker with the last
        # used source selected.
        if source is None:
            source = "Wifi"
        await self.set_source(source)


class SyncKefSpeaker:
    """A synchronous KEF speaker class.

    This has the same methods as `AsyncKefSpeaker`, however, it wraps all async
    methods and call them in a blocking way."""

    def __init__(self, async_speaker):
        self.async_speaker = async_speaker

    def __getattr__(self, attr):
        method = getattr(self.async_speaker, attr)
        if method is None:
            raise AttributeError(f"'SyncKefSpeaker' object has no attribute '{attr}.'")
        if inspect.iscoroutinefunction(method):

            @functools.wraps(method)
            def wrapped(*args, **kwargs):
                return asyncio.run(method(*args, **kwargs))

            return wrapped
        else:
            return method


host = "192.168.31.196"
port = 50001
s = AsyncKefSpeaker(host, port)
