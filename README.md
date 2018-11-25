# Python interface to control KEF speakers
Supported: KEF LS50 Wireless (Requires [firmware](http://international.kef.com/product-support) June 2018 or later)

Untested: KEF LSX

## Features supported
- Get and set volume
- Mute and Unmute
- Get and set source input
- Get if the speakers are online
- Automatically connects and disconnects when speakers goes online/offline
- Turn off speaker

## Features unfortunatly unsupported
- Turn on is impossible over tcp/ip because the speaker turns off network interface when turned off. This is true for LS50 Wireless. LSX should be possible to turn on.

Note: One workaround to turning on is to use IR commands to turn on. I have included a [lirc config](lirc/KEF_LS50_WIRELESS.lircd) with all the keys on the remote. Note that each command has to be sent twice to work (at least for me).

## Install
```bash
pip install pykef
```

## Discussion
See [home assistant thread](https://community.home-assistant.io/t/kef-ls50-wireless/)

## Examples
Setup:
```python
host = '192.168.1.200'
port = 50001
speaker = KefSpeaker(host, port)
```
Set volume:
```python
speaker.volume = 0.5 # %50 vol
```
Get volume:
```python
volume = speaker.volume
```
Set source:
```python
speaker.source = InputSource.AUX
```
Get source:
```python
source = speaker.source
```
Mute:
```python
speaker.volume = None
# Or
speaker.muted = True
```
Unmute (set to volume before mute):
```python
speaker.muted = False
```
Step volume up
```python
speaker.increseVolume() # 5% increase
speaker.increseVolume(0.10) # 10% increase
```
Step volume down
```python
speaker.decreaseVolume() # 5% increase
speaker.decreaseVolume(0.10) # 10% increase
```
Turn off
```python
speaker.turnOff()
```

## How to

### Upload new release:
1. Update needed tools:
```bash
python3 -m pip install --user --upgrade setuptools wheel
```
2. Build
```bash
python3 setup.py sdist bdist_wheel
```
3. Upload (test)
```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

## License
MIT License

## Authors
- Robin Grönberg
