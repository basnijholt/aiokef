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


class Speaker:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.queue = queue.Queue()
        self.ioloop = asyncio.get_event_loop()
        self.reader, self.writer = (None, None)
        self._last_time = 0
        self.task = self.ioloop.create_task(self.run())

    @property
    def is_connected(self):
        return (self.reader, self.writer) != (None, None)

    async def ensure_connection(self):
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
                self._online = False
                raise ConnectionRefusedError("Speaker is offline.") from e
            else:
                self._online = True
                self._last_time = time.time()
                return
            retries += 1
        self._online = False
        raise ConnectionRefusedError("Connection tries exceeded")

    async def send_message(self, message):
        self.writer.write(message)
        await self.writer.drain()

        read_task = self.reader.read(100)
        try:
            data = await asyncio.wait_for(read_task, timeout=1)
            self._last_time = time.time()
            return data[-2]
        except asyncio.TimeoutError:
            print("Timeout")

    async def disconnect(self):
        if self.is_connected:
            print("Disconnecting")
            self.writer.close()
            await self.writer.wait_closed()
            self.reader, self.writer = (None, None)

    async def run(self):
        while True:
            if not self.queue.empty():
                await self.ensure_connection()
                message = self.queue.get()
                reply = await self.send_message(message)
                print(f"Received: {reply}")
            else:
                await asyncio.sleep(0.1)
                if time.time() - self._last_time > _KEEP_ALIVE:
                    await self.disconnect()


host = "192.168.31.196"
port = 50001
s = Speaker(host, port)
