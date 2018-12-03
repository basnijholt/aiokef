#! /usr/bin/env python
"""pykef is the library for interfacing with kef speakers"""

from enum import Enum
import socket
import logging
import datetime
import select
from time import sleep, time
from threading import Thread, Semaphore

_LOGGER = logging.getLogger(__name__)
_VOL_STEP = 0.05  # 5 percent
_RESPONSE_OK = 17
_TIMEOUT = 1.0  # in secs
_KEEP_ALIVE = 1.0  # in secs
_SCALE = 100.0
_RETRIES = 10
_WAIT_FOR_ONLINE_STATE = 30.0


class Volume(Enum):
    Mute = "MUTE"
    Unmute = "UNMUTE"


class InputSource(Enum):
    Wifi = bytes([0x53, 0x30, 0x81, 0x12, 0x82])
    Bluetooth = bytes([0x53, 0x30, 0x81, 0x19, 0xad])
    Aux = bytes([0x53, 0x30, 0x81, 0x1a, 0x9b])
    Opt = bytes([0x53, 0x30, 0x81, 0x1b, 0x00])
    Usb = bytes([0x53, 0x30, 0x81, 0x1c, 0xf7])

    def __str__(self):
        return {
            InputSource.Wifi: "Wifi",
            InputSource.Bluetooth: "Bluetooth",
            InputSource.Aux: "Aux",
            InputSource.Opt: "Opt",
            InputSource.Usb: "Usb",
        }[self]

    @classmethod
    def from_str(cls, name):
        matches = [s for s in InputSource if str(s).endswith(name)]
        return matches[0] if matches else None


class States(Enum):
    """States for the a KefClientDevice."""

    Online = 1
    Offline = 2
    TurningOff = 3


class Cache:
    """Holds some variable and store in cache for some time if set."""

    def __init__(self, initial_value, get_function, cache_timeout=1.0):
        """ Initialize cache variable holder.

        initial_value: The initial value for the cache varaible
        cache_timeout: How many secs the cache value should be used before
        using a real getter.

        """
        self.__value = initial_value
        self.__current_timeout = time()
        self.__cache_timeout = cache_timeout
        self.__get_function = get_function

    def get(self):
        if self.__current_timeout - time() < 0:
            self.__value = self.__get_function()
        return self.__value

    def set(self, value, update_cache_timeout=True):
        if update_cache_timeout:
            self.__current_timeout = time() + self.__cache_timeout
        self.__value = value


class KefSpeaker():
    def __init__(self, host, port):
        self.__semaphore = Semaphore()
        self.__socket = None
        self.__connected = False
        self.__last_timestamp = 0
        self.__host = host
        self.__port = port

        self.__state = Cache(None, self.__getState, _WAIT_FOR_ONLINE_STATE)
        self.__volume = Cache(None, self.__getVolume)
        self.__source = Cache(None, self.__getSource)

        self.__update_thread = Thread(target=self.__update, daemon=True)
        self.__update_thread.start()

    def __refresh_connection(self):
        """Connect if not connected.

        Retry at max for 100 times, with longer interval each time.
        Update timestamp that keep connection alive.

        If unable to connect due to no route to host, set to offline

        If speaker is offline, max retires is infinite.

        """
        def setup_connection():
            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.__socket.settimeout(_TIMEOUT)
            return self.__socket
        self.__last_timestamp = time()

        if not self.__connected:
            self.__socket = setup_connection()
            self.__connected = False
            wait = 0.1
            retries = 0
            while retries < _RETRIES:
                self.__last_timestamp = time()
                try:
                    self.__socket.connect((self.__host, self.__port))
                    self.__connected = True
                    _LOGGER.debug("Online")
                    _LOGGER.debug("Connected")
                    break
                except ConnectionRefusedError:
                    self.__socket = setup_connection()
                    wait += 0.1
                    sleep(wait)
                except BlockingIOError:  # Connection ingoing
                    retries = 0
                    wait = _TIMEOUT
                    sleep(wait)
                except OSError as err:  # Host is down
                    _LOGGER.debug("Offline")
                    raise ConnectionRefusedError("Speaker is offline") from err
                except socket.timeout:  # Host went offline (probably)
                    _LOGGER.debug("Offline")
                    raise ConnectionRefusedError("Speaker is offline") from err
                retries += 1

    def __disconnect_if_passive(self):
        """Disconnect if connection is not used for a while (old timestamp)."""
        should_disconnect = time() - self.__last_timestamp > _KEEP_ALIVE
        if self.__connected and should_disconnect:
            self.__connected = False
            self.__socket.close()
            _LOGGER.debug("Disconneced")

    def __update(self):
        """Update speakers, disconnects speakers when passive."""
        while 1:
            sleep(0.1)
            self.__disconnect_if_passive()

    def __sendCommand(self, message):
        """Send command to speakers, returns the response."""
        self.__refresh_connection()
        if self.__connected:
            self.__semaphore.acquire()
            try:
                self.__socket.sendall(message)
                self.__socket.setblocking(0)
                ready = select.select([self.__socket], [], [], _TIMEOUT)
                if ready[0]:
                    data = self.__socket.recv(1024)
                else:
                    data = None
                self.__socket.setblocking(1)
            except Exception as err:
                raise OSError('__sendCommand failed') from err
            finally:
                self.__semaphore.release()
        else:
            raise OSError('__sendCommand failed')
        return data[len(data) - 2] if data else None

    def __wait_for_online_state(self, time_to_wait=_WAIT_FOR_ONLINE_STATE):
        """Use this function to wait for online state."""
        while time_to_wait > 0 and self.__state.get() is not States.Online:
            time_to_sleep = 0.1
            time_to_wait -= time_to_sleep
            sleep(time_to_sleep)

    def __getVolume(self, scale=True):
        _LOGGER.debug("__getVolume")
        msg = bytes([0x47, 0x25, 0x80, 0x6c])
        volume = self.__sendCommand(msg)
        if volume:
            scaled_volume = volume / _SCALE if volume < 128 else Volume.Mute
            return scaled_volume if scale else volume
        else:
            raise ConnectionRefusedError("Cannot fetch volume from speaker")

    def __setVolume(self, volume):
        _LOGGER.debug("__setVolume: " + "volume:" + str(volume))
        if not volume:
            return
        if volume not in [Volume.Mute, Volume.Unmute]:
            set_volume = int(max(0.0, min(1.0, volume)) * _SCALE)
        else:
            should_mute = volume is Volume.Mute
            current_volume = self.__getVolume(scale=False)
            if current_volume:
                set_volume = int(current_volume) % 128 + (128 * should_mute)
        # write vol level in 4th place , add 128 to current level to mute
        msg = bytes([0x53, 0x25, 0x81, int(set_volume), 0x1a])
        return self.__sendCommand(msg) == _RESPONSE_OK

    def __getSource(self):
        _LOGGER.debug("__getSource")
        msg = bytes([0x47, 0x30, 0x80, 0xd9])
        table = {
            18: InputSource.Wifi,
            25: InputSource.Bluetooth,
            26: InputSource.Aux,
            27: InputSource.Opt,
            28: InputSource.Usb,
            31: InputSource.Bluetooth,
        }
        response = self.__sendCommand(msg)

        return table.get(response) if response else None

    def __setSource(self, source):
        _LOGGER.debug("__setSource: " + "source:" + str(source))
        return self.__sendCommand(source.value) == _RESPONSE_OK

    def __getState(self):
        state = States.Online
        try:
            self.__refresh_connection()
        except Exception:
            state = States.Offline
        return state

    @property
    def volume(self):
        """Volume level of the media player (0..1). None if muted"""
        value = self.__volume.get()
        if value:
            self.__volume.set(value, update_cache_timeout=False)
        return value

    @volume.setter
    def volume(self, value):
        self.__wait_for_online_state()
        success = self.__setVolume(value)
        if success and value is not Volume.Unmute:
            self.__volume.set(value)

    @property
    def source(self):
        """Get the input source of the speaker."""
        value = self.__source.get()
        if value:
            self.__source.set(value, update_cache_timeout=False)
        return value

    @source.setter
    def source(self, value):
        self.__wait_for_online_state()
        success = self.__setSource(value)
        if success:
            self.__source.set(value)

    @property
    def muted(self):
        return self.volume is Volume.Mute

    @muted.setter
    def muted(self, value):
        self.volume = Volume.Mute if value else Volume.Unmute

    @property
    def online(self):
        return self.__state.get() is States.Online

    def turnOff(self):
        msg = bytes([0x53, 0x30, 0x81, 0x9b, 0x0b])
        success = self.__sendCommand(msg) == _RESPONSE_OK
        if success:
            self.__state.set(States.TurningOff)

    def increaseVolume(self, step=None):
        """Increase volume by step, or 5% by default.

        Constrait: 0.0 < step < 1.0.
        """
        volume = self.volume
        if volume:
            step = step if step else _VOL_STEP
            self.volume = volume + step

    def decreaseVolume(self, step=None):
        """Decrease volume by step, or 5% by default.

        Constrait: 0.0 < step < 1.0.
        """
        self.increaseVolume(-(step or _VOL_STEP))


def mainTest1():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)
    # print(speaker.__setSource(InputSource.Opt))
    # print(speaker.__getSource())

    # TIMER = 0.1
    # sleep(TIMER)
    # speaker.connect(host, port)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    speaker.source = InputSource.Usb
    print("isOnline:" + str(speaker.online))
    print(speaker.source)
    speaker.volume = 0.5
    print(speaker.volume)
    #print ("vol:" + str(speaker.increaseVolume()))
    speaker.volume = None
    #print("getvol: ", speaker.__getVolume())
    speaker.muted = False
    print("getvol: ", speaker.volume)
    speaker.volume = 0.6
    print("getvol: ", speaker.volume)
    print("vol: ", speaker.volume)
    print("getvol: ", speaker.volume)
    print("vol up:" + str(speaker.increaseVolume(0.05)))
    print("getvol: ", speaker.volume)
    print("vol: ", speaker.volume)
    speaker.increaseVolume()
    print("vol up:" + str(speaker.volume))
    speaker.increaseVolume()
    print("vol up:" + str(speaker.volume))
    speaker.volume = None
    speaker.increaseVolume()
    print("vol up:" + str(speaker.volume))
    speaker.muted = False
    print("vol: ", speaker.volume)
    speaker.decreaseVolume()
    print("vol down:" + str(speaker.volume))
    speaker.decreaseVolume()
    print("vol down:" + str(speaker.volume))
    speaker.decreaseVolume()
    print("vol down:" + str(speaker.volume))

    while 1:
        sleep(3)
        print(speaker.source)


def mainTest2():
    host = '192.168.178.52'
    port = 50001
    service = KefSpeaker(host, port)
    print("isOnline:" + str(service.online))
    service.source = InputSource.Usb
    service.source = InputSource(("USB",))
    # service.turnOff()


def mainTest3():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)

    while 1:
        sleep(2)
        print("vol:" + str(speaker.volume))
        print("mute:" + str(speaker.muted))
        print("source:" + str(speaker.source))
        print("online:" + str(speaker.online))


def mainTest4():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)

    while 1:

        speaker.muted = True
        print("Is Mutted:" + str(speaker.muted))
        sleep(5)
        speaker.muted = False
        print("Is Mutted:" + str(speaker.muted))
        sleep(5)


def mainTest5():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)

    while 1:
        # speaker.increaseVolume(0.1)
        print("Volume:" + str(speaker.volume))
        sleep(5)
        # speaker.decreaseVolume(0.1)
        print("Volume:" + str(speaker.volume))
        sleep(5)

        #speaker.muted = True
        print("Is Mutted:" + str(speaker.muted))
        # sleep(5)
        #speaker.muted = False
        #print("Is Mutted:" + str(speaker.muted))
        # sleep(5)

        sleep(5)


if __name__ == '__main__':
    mainTest3()
