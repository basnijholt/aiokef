import asyncio
import functools
import logging
import queue
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


class _Communicator:
    def __init__(self, host, port, *, ioloop=None):
        self.host = host
        self.port = port
        self.queue = asyncio.Queue()
        self.replies = asyncio.Queue()
        self.reader, self.writer = (None, None)
        self.last_time = 0
        self.is_online = False
        self.ioloop = ioloop or asyncio.get_event_loop()
        self.task = self.ioloop.create_task(self.run())
        self.disconnect_task = self.ioloop.create_task(self.disconnect_if_passive())

    @property
    def is_connected(self):
        return (self.reader, self.writer) != (None, None)

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
                self.reader, self.writer = await asyncio.wait_for(
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
                self.is_online = False
                raise ConnectionRefusedError("Speaker is offline.") from e
            else:
                self.is_online = True
                self.last_time = time.time()
                return
            retries += 1
        self.is_online = False
        raise ConnectionRefusedError("Connection tries exceeded")

    async def _send_message(self, message):
        self.writer.write(message)
        await self.writer.drain()

        read_task = self.reader.read(100)
        try:
            data = await asyncio.wait_for(read_task, timeout=1)
            self.last_time = time.time()
            return data[-2]
        except asyncio.TimeoutError:
            print("Timeout")

    async def disconnect(self):
        if self.is_connected:
            print("Disconnecting")
            self.writer.close()
            await self.writer.wait_closed()
            self.reader, self.writer = (None, None)

    async def disconnect_if_passive(self):
        """Disconnect socket after _KEEP_ALIVE seconds of not using it."""
        while True:
            time_is_up = time.time() - self.last_time > _KEEP_ALIVE
            if self.is_connected and time_is_up:
                await self.disconnect()
            await asyncio.sleep(0.05)

    async def run(self):
        while True:
            msg = await self.queue.get()
            try:
                await self.open_connection()
            except ConnectionRefusedError as e:
                print(f"Error in main loop: {e}")
                continue
            reply = await self._send_message(msg)
            await self.replies.put(reply)
            print(f"Received: {reply}")

    async def send_message(self, msg):
        await self.queue.put(msg)
        return await self.replies.get()

    def send_message_blocking(self, msg):
        """Send a message and return the reply (blocking)."""
        reply = self.ioloop.run_until_complete(self.send_message(msg))
        return reply


host = "192.168.31.196"
port = 50001
s = _Communicator(host, port)


vol = lambda volume: bytes([0x53, 0x25, 0x81, int(volume), 0x1A])

t = s.send_message_blocking(vol(40))
print(t)
