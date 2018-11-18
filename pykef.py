#! /usr/bin/env python
"""The main service script for pykef"""

from enum import Enum
import socket
import logging

_LOGGER = logging.getLogger(__name__)
_VOL_STEP = 5.0 / 128.0
_TURN_OFF_CMD = bytes([0x53, 0x30, 0x81, 0x9b, 0x0b])
_RESPONSE_OK = 17
_TIMEOUT = 5

class InputSource(Enum):
    WIFI = bytes([0x53, 0x30, 0x81, 0x12, 0x82])
    BLUETOOTH = bytes([0x53, 0x30, 0x81, 0x19, 0xad])
    AUX = bytes([0x53, 0x30, 0x81, 0x1a, 0x9b])
    OPT = bytes([0x53, 0x30, 0x81, 0x1b, 0x00])
    USB = bytes([0x53, 0x30, 0x81, 0x1c, 0xf7])

class KefServiceException(Exception):
    pass

class KefService():
    def __init__(self):
        self.__connection = None
        self.__host = None
        self.__port = None
        self.__volume = 0
        self.__input_source = None
        try:
            self.__connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as err:
            print(err)

    def connect(self, host, port, on_connect = None, on_disconnect = None):
        self.__host = host
        self.__port = port
        self.__connection.settimeout(_TIMEOUT)
        try:
            self.__connection.connect((self.__host, self.__port))
        except Exception as err:
            msg = 'Unable to connect to kef speaker at {}. Is it offline?'.format(host)
            raise KefServiceException(msg) from err
        if self.isConnected():
            self.__volume = self._getVolume()

    def turnOff(self):
        msg = bytes(_TURN_OFF_CMD)
        self._sendCommand(msg)

    def isConnected(self):
        return self.__connection is not None

    @property
    def volume(self):
        """Volume level of the media player (0..1). None if muted"""
        return self.__volume / 128.0 if self.__volume < 128 else None

    @volume.setter
    def volume(self, value):
        if value:
            volume = int(max(0.0,min(1.0, value)) * 128.0)
        else:
            volume = int(self.__volume) % 128 + 128
        self._setVolume(volume)

    @property
    def source(self):
        """Get the input source of the speaker."""
        return self.__input_source

    @source.setter
    def source(self, value):
        self._setSource(value)

    @property
    def muted(self):
        return self.__volume > 128

    def increaseVolume(self):
        self._getVolume()
        if not self.muted:
            self.volume += _VOL_STEP
        return self.volume

    def decreaseVolume(self):
        self._getVolume()
        if not self.muted:
            self.volume -= _VOL_STEP
        return self.volume

    def _getVolume(self):
        _LOGGER.debug("_getVolume" )
        MESSAGE = bytes([0x47, 0x25, 0x80, 0x6c])
        self.__volume = self._sendCommand(MESSAGE)
        return self.__volume

    def _setVolume(self, volume):
        _LOGGER.debug("_setVolume: " + "volume:" + str(volume))
        ## write vol level in 4th place , add 128 to current level to mute
        MESSAGE = bytes([0x53, 0x25, 0x81, volume, 0x1a])
        response = self._sendCommand(MESSAGE)
        if response == _RESPONSE_OK:
            self.__volume = volume
        return self.__volume

    def _setSource(self, source):
        reponse = self._sendCommand(source.value)
        if reponse == _RESPONSE_OK:
            self.__input_source = source
        return self.__input_source

    def _getSource(self):
        # TODO: figure out how to fetch the input source from the speaker
        return self.__input_source or InputSource.WIFI

    def mute(self):
        self.volume = None

    def unmute(self):
        self._setVolume(int(self._getVolume()) % 128)

    def _sendCommand (self,message):
        if self.isConnected() == False:
            _LOGGER.warning("LS50 not connected ")
            return None
        connection = self.__connection
        connection.sendall(message)
        data = connection.recv(1024)
        return self._parseResponse(data);

    def _parseResponse(self, message):
        return message[len(message) - 2]


def mainTest2():
    host = '192.168.1.200'
    port = 50001
    service = KefService()
    service.connect(host, port)
    print ("isConnected:" + str(service.isConnected()))
    service.turnOff()

def mainTest1():
    host = '192.168.1.200'
    port = 50001
    service = KefService()
    service.connect(host, port)
    print ("isConnected:" + str(service.isConnected()))
    print(service.source)
    service.source = InputSource.USB
    print(service.source)
    service.volume = 0.5
    print(service.volume)
    print(service._getVolume())
    #print ("vol:" + str(service.increaseVolume()))
    service.volume = None
    #print("getvol: ", service._getVolume())
    service.unmute()
    print("getvol: ", service._getVolume())
    #print(service._setVolume(80))
    print("getvol: ", service._getVolume())
    print("vol: ", service.volume)
    print("getvol: ", service._getVolume())
    print ("vol up:" + str(service.increaseVolume()))
    print("getvol: ", service._getVolume())
    print("vol: ", service.volume)
    print ("vol up:" + str(service.increaseVolume()))
    print ("vol up:" + str(service.increaseVolume()))
    service.volume = None
    print ("vol up:" + str(service.increaseVolume()))
    service.unmute()
    print("vol: ", service.volume)
    print ("vol down:" + str(service.decreaseVolume()))
    print ("vol down:" + str(service.decreaseVolume()))
    print ("vol down:" + str(service.decreaseVolume()))
    print ("vol down:" + str(service.decreaseVolume()))


if __name__ == '__main__':
    mainTest1()
