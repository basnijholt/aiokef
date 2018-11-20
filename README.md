# Python interface to control KEF speakers
Supported: KEF LS50 Wireless

Untested: KEF LSX

## Features supported
- Get and set volume
- Get and set source input
- Get if the speakers are online
- Automatically connects and disconnects when speakers goes online/offline

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
3. Upload
```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

## License
MIT License

## Authors
- Robin Grönberg
