"""A module for asynchronously interacting with KEF wireless speakers."""

import asyncio
import functools
import inspect
import logging
import socket
import time
from typing import Any, Optional, Tuple, Union

from tenacity import before_log, retry, stop_after_attempt, wait_exponential

_LOGGER = logging.getLogger(__name__)
_RESPONSE_OK = 17
_TIMEOUT = 2.0  # in seconds
_KEEP_ALIVE = 20  # in seconds
_VOLUME_SCALE = 100.0
_MAX_ATTEMPT_TILL_SUCCESS = 5
_MAX_SEND_MESSAGE_TRIES = 5
_MAX_CONNECTION_RETRIES = 10  # Each time `_send_command` is called, ...
# ... the connection is maximally refreshed this many times.

# The first number is used for setting the source.
INPUT_SOURCES = {"Wifi": 18, "Bluetooth": 25, "Aux": 26, "Opt": 27, "Usb": 28}

INPUT_SOURCES_RESPONSE = {v: k for k, v in INPUT_SOURCES.items()}
# Only in the case of Bluetooth there is a second number
# that can identify if the bluetooth is connected. Where
# 25 is connected and 31 is not_connected.
INPUT_SOURCES_RESPONSE[31] = "Bluetooth"

_SET_START = ord("S")
_SET_MID = 129
_GET_MID = 128
_GET_START = ord("G")
_SOURCE = ord("0")
_VOL = ord("%")

COMMANDS = {
    "set_volume": lambda volume: bytes([_SET_START, _VOL, _SET_MID, int(volume)]),
    "set_source": lambda i: bytes([_SET_START, _SOURCE, _SET_MID, i]),
    "get_volume": bytes([_GET_START, _VOL, _GET_MID]),
    "get_source": bytes([_GET_START, _SOURCE, _GET_MID]),
}


class _AsyncCommunicator:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        ioloop: Optional[asyncio.events.AbstractEventLoop] = None,
    ):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._last_time_stamp = 0.0
        self._is_online = False
        self._ioloop = ioloop or asyncio.get_event_loop()
        self._disconnect_task = self._ioloop.create_task(self._disconnect_if_passive())

    @property
    def is_connected(self) -> bool:
        return (self._reader, self._writer) != (None, None)

    async def open_connection(self) -> None:
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

    async def _send_message(self, message: bytes) -> int:
        assert self._writer is not None
        assert self._reader is not None
        _LOGGER.debug(f"Writing message: {str(message)}")
        self._writer.write(message)
        await self._writer.drain()

        _LOGGER.debug("Reading message")
        read_task = self._reader.read(100)
        try:
            data = await asyncio.wait_for(read_task, timeout=_TIMEOUT)
            _LOGGER.debug(f"Got reply, {str(data)}")
            self._last_time_stamp = time.time()
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout in waiting for reply")
        finally:
            return data[-2]

    async def _disconnect(self) -> None:
        if self.is_connected:
            assert self._writer is not None
            _LOGGER.debug("Disconnecting")
            self._writer.close()
            await self._writer.wait_closed()
            self._reader, self._writer = (None, None)

    async def _disconnect_if_passive(self) -> None:
        """Disconnect socket after _KEEP_ALIVE seconds of not using it."""
        while True:
            time_is_up = time.time() - self._last_time_stamp > _KEEP_ALIVE
            if self.is_connected and time_is_up:
                await self._disconnect()
            await asyncio.sleep(1)

    @retry(
        stop=stop_after_attempt(_MAX_SEND_MESSAGE_TRIES),
        wait=wait_exponential(exp_base=1.5),
        before=before_log(_LOGGER, logging.DEBUG),
    )
    async def send_message(self, msg) -> int:
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
    sync : `aiokef.SyncKefSpeaker`
        Run any method that the `AsyncKefSpeaker` has in a synchronous way.
        For example ``kef_speaker.sync.mute()``.
    """

    def __init__(
        self,
        host: str,
        port: int = 50001,
        volume_step: float = 0.05,
        maximum_volume: float = 1.0,
        *,
        ioloop: Optional[asyncio.events.AbstractEventLoop] = None,
    ):
        self.host = host
        self.port = port
        self.volume_step = volume_step
        self.maximum_volume = maximum_volume
        self._comm = _AsyncCommunicator(host, port, ioloop=ioloop)
        self.sync = SyncKefSpeaker(self)

    @retry(
        stop=stop_after_attempt(_MAX_ATTEMPT_TILL_SUCCESS),
        wait=wait_exponential(exp_base=1.5),
        before=before_log(_LOGGER, logging.DEBUG),
    )
    async def get_source_and_state(self) -> Tuple[str, bool]:
        # If the speaker is off, the source increases by 128
        response = await self._comm.send_message(COMMANDS["get_source"])
        is_on = response <= 128
        source = INPUT_SOURCES_RESPONSE.get(response % 128)
        if source is None:
            raise ConnectionError("Getting source failed, got response {response}.")
        return source, is_on

    async def get_source(self) -> None:
        source, _ = await self.get_source_and_state()
        return source

    @retry(
        stop=stop_after_attempt(_MAX_ATTEMPT_TILL_SUCCESS),
        wait=wait_exponential(exp_base=1.5),
        before=before_log(_LOGGER, logging.DEBUG),
    )
    async def set_source(self, source: str, *, state="on") -> None:
        assert source in INPUT_SOURCES
        i = INPUT_SOURCES[source] % 128
        if state == "off":
            i += 128
        response = await self._comm.send_message(
            COMMANDS["set_source"](i)  # type: ignore
        )
        if response != _RESPONSE_OK:
            raise ConnectionError(f"Setting source failed, got response {response}.")

        for _ in range(_MAX_ATTEMPT_TILL_SUCCESS):
            current_source = await self.get_source()
            if current_source == source:
                return
            _LOGGER.debug(f"Source is {current_source} but {source} is selected")
            await asyncio.sleep(0.5)

    @retry(
        stop=stop_after_attempt(_MAX_ATTEMPT_TILL_SUCCESS),
        wait=wait_exponential(exp_base=1.5),
        before=before_log(_LOGGER, logging.DEBUG),
    )
    async def get_volume_and_is_muted(
        self, scale=True
    ) -> Tuple[Union[float, int], bool]:
        """Return volume level (0..1) and is_muted (in a single call)."""
        volume = await self._comm.send_message(COMMANDS["get_volume"])
        if volume is None:
            raise ConnectionError("Getting volume failed.")
        is_muted = volume >= 128
        return volume / _VOLUME_SCALE if scale else volume, is_muted

    @retry(
        stop=stop_after_attempt(_MAX_ATTEMPT_TILL_SUCCESS),
        wait=wait_exponential(exp_base=1.5),
        before=before_log(_LOGGER, logging.DEBUG),
    )
    async def _set_volume(self, volume: int) -> None:
        # Write volume level (0..100) on index 3,
        # add 128 to current level to mute.
        response = await self._comm.send_message(
            COMMANDS["set_volume"](volume)  # type: ignore
        )
        if response != _RESPONSE_OK:
            raise ConnectionError(
                f"Setting the volume failed, got response {response}."
            )

    async def get_volume(self) -> Optional[float]:
        """Volume level of the media player (0..1). None if muted."""
        volume, is_muted = await self.get_volume_and_is_muted(scale=True)
        return volume if not is_muted else None

    async def set_volume(self, value: float) -> float:
        volume = max(0.0, min(self.maximum_volume, value))
        await self._set_volume(int(volume * _VOLUME_SCALE))
        return volume

    async def _change_volume(self, step: float) -> float:
        """Change volume by `step`."""
        volume = await self.get_volume()
        is_muted = await self.is_muted()
        if is_muted:
            await self.unmute()
        assert volume is not None
        return await self.set_volume(volume + step)

    async def increase_volume(self) -> float:
        """Increase volume by `self.volume_step`."""
        return await self._change_volume(self.volume_step)

    async def decrease_volume(self) -> float:
        """Decrease volume by `self.volume_step`."""
        return await self._change_volume(-self.volume_step)

    async def is_muted(self) -> bool:
        _, is_muted = await self.get_volume_and_is_muted(scale=False)
        return is_muted

    async def mute(self) -> None:
        volume, _ = await self.get_volume_and_is_muted(scale=False)
        await self._set_volume(int(volume) % 128 + 128)

    async def unmute(self) -> None:
        volume, _ = await self.get_volume_and_is_muted(scale=False)
        await self._set_volume(int(volume) % 128)

    async def is_online(self) -> bool:
        try:
            await self._comm.open_connection()
        except ConnectionRefusedError:
            assert not self._comm._is_online
        finally:
            return self._comm._is_online

    async def is_on(self) -> bool:
        _, is_on = await self.get_source_and_state()
        return is_on

    async def turn_on(self, source: Optional[str] = None) -> None:
        """The speaker can be turned on by selecting an INPUT_SOURCE."""
        source, is_on = await self.get_source_and_state()
        if is_on:
            return
        await self.set_source(source, state="on")

        for _ in range(_MAX_ATTEMPT_TILL_SUCCESS):
            if await self.is_on():
                _LOGGER.debug("Speaker is on")
                return
            _LOGGER.debug("Turned on the speaker, but it is still off")
            await asyncio.sleep(1)

    async def turn_off(self) -> None:
        source, is_on = await self.get_source_and_state()
        if not is_on:
            return
        await self.set_source(source, state="off")

        for _ in range(_MAX_ATTEMPT_TILL_SUCCESS):
            if not await self.is_on():
                _LOGGER.debug("Speaker is off")
                return
            _LOGGER.debug("Turned off the speaker, but it is still on")
            await asyncio.sleep(1)


class SyncKefSpeaker:
    """A synchronous KEF speaker class.

    This has the same methods as `aiokef.AsyncKefSpeaker`, however, it wraps all async
    methods and call them in a blocking way."""

    def __init__(self, async_speaker: AsyncKefSpeaker):
        self.async_speaker = async_speaker

    def __getattr__(self, attr: str) -> Any:
        method = getattr(self.async_speaker, attr)
        if method is None:
            raise AttributeError(f"'SyncKefSpeaker' object has no attribute '{attr}.'")
        if inspect.iscoroutinefunction(method):

            @functools.wraps(method)
            def wrapped(*args, **kwargs):
                return self.ioloop.run_until_complete(method(*args, **kwargs))

            return wrapped
        else:
            return method
