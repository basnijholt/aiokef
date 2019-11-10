"""A module for interacting with KEF wireless speakers."""

import asyncio
import contextlib
import functools
import logging
import select
import socket
import time

_LOGGER = logging.getLogger(__name__)
_RESPONSE_OK = 17
_TIMEOUT = 1.0  # in seconds
_KEEP_ALIVE = 1.0  # in seconds
_VOLUME_SCALE = 100.0
_MAX_SEND_COMMAND_TRIES = 5
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


class AsyncKefSpeaker:
    def __init__(self, host, port, *, ioloop=None):
        self.host = host
        self.port = port
        self._queue = asyncio.Queue()
        self._replies = asyncio.Queue()
        self._reader, self._writer = (None, None)
        self._last_time_stamp = 0
        self._is_online = False
        self._ioloop = ioloop or asyncio.get_event_loop()
        self._run_task = self._ioloop.create_task(self._run())
        self._disconnect_task = self._ioloop.create_task(self._disconnect_if_passive())

    @property
    def is_connected(self):
        return (self._reader, self._writer) != (None, None)

    async def open_connection(self):
        if self.is_connected:
            return
        retries = 0
        while retries < _MAX_CONNECTION_RETRIES:
            print("Opening connection")
            try:
                task = asyncio.open_connection(
                    self.host, self.port, family=socket.AF_INET
                )
                self._reader, self._writer = await asyncio.wait_for(
                    task, timeout=_TIMEOUT
                )
            except ConnectionRefusedError:
                print("Opening connection failed")
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
        self._writer.write(message)
        await self._writer.drain()

        read_task = self._reader.read(100)
        try:
            data = await asyncio.wait_for(read_task, timeout=1)
            self._last_time_stamp = time.time()
            return data[-2]
        except asyncio.TimeoutError:
            print("Timeout")

    async def disconnect(self):
        if self.is_connected:
            print("Disconnecting")
            self._writer.close()
            await self._writer.wait_closed()
            self._reader, self._writer = (None, None)

    async def _disconnect_if_passive(self):
        """Disconnect socket after _KEEP_ALIVE seconds of not using it."""
        while True:
            time_is_up = time.time() - self._last_time_stamp > _KEEP_ALIVE
            if self.is_connected and time_is_up:
                await self.disconnect()
            await asyncio.sleep(0.05)

    async def _run(self):
        while True:
            msg = await self._queue.get()
            try:
                await self.open_connection()
            except ConnectionRefusedError as e:
                print(f"Error in main loop: {e}")
                continue
            reply = await self._send_message(msg)
            await self._replies.put(reply)
            print(f"Received: {reply}")

    async def send_message(self, msg):
        await self._queue.put(msg)
        return await self._replies.get()

    async def get_source(self):
        response = await self.send_message(COMMANDS["get_source"])
        source = INPUT_SOURCES_RESPONSE.get(response)
        if source is None:
            raise ConnectionError("Getting source failed, got response {response}.")
        return source

    async def set_source(self, source: str):
        assert source in INPUT_SOURCES
        response = await self.send_message(INPUT_SOURCES[source]["msg"])
        if response != _RESPONSE_OK:
            raise ConnectionError("Setting source failed, got response {response}.")

    async def _get_volume(self, scale=True):
        volume = await self.send_message(COMMANDS["get_volume"])
        if volume is None:
            raise ConnectionError("Getting volume failed.")
        return volume / _VOLUME_SCALE if scale else volume

    async def _set_volume(self, volume: int):
        # Write volume level (0..100) on index 3,
        # add 128 to current level to mute.
        response = await self.send_message(COMMANDS["set_volume"](volume))
        if response != _RESPONSE_OK:
            raise ConnectionError(
                f"Setting the volume failed, got response {response}."
            )

    async def turn_off(self):
        response = await self.send_message(COMMANDS["turn_off"])
        if response != _RESPONSE_OK:
            raise ConnectionError("Turning off failed, got response {response}.")

    async def get_volume(self) -> float:
        """Volume level of the media player (0..1). None if muted."""
        volume = await self._get_volume(scale=True)
        return volume if not (await self.is_muted()) else None

    async def set_volume(self, value: float):
        volume = int(max(0.0, min(self.maximum_volume, value)) * _VOLUME_SCALE)
        await self._set_volume(volume)

    async def _change_volume(self, step: float):
        """Change volume by `step`."""
        volume = await self.get_volume()
        if not self.is_muted():
            new_volume = volume + step
            await self.set_volume(new_volume)
            return new_volume

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

    @property
    def is_online(self) -> bool:
        # This is a property because `_refresh_connection` is very fast, ~5 ms.
        with contextlib.suppress(Exception):
            self._ioloop.run_until_complete(self.open_connection())
        return self._is_online

    async def turn_on(self, source=None):
        """The speaker can be turned on by selecting an INPUT_SOURCE."""
        # XXX: it might be possible to turn on the speaker with the last
        # used source selected.
        if source is None:
            source = "Wifi"
        await self.set_source(source)

    def blocking_method(self, method: str, args=()):
        return self._ioloop.run_until_complete(getattr(self, method)(*args))


host = "192.168.31.196"
port = 50001
s = AsyncKefSpeaker(host, port)


vol = lambda volume: bytes([0x53, 0x25, 0x81, int(volume), 0x1A])

t = s.blocking_method("send_message", (vol(40),))
print(t)
