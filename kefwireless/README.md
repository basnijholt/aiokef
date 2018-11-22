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
- Turn on speaker (via HA service call)

## Features unfortunatly unsupported
- Turn on is impossible over tcp/ip because the speaker turns off network interface when turned off. This is true for LS50 Wireless. LSX should be possible to turn on.
- LS50 speakers take about 20 secongs to boot. Thus, after turning them on please be patient. 


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

### Use in Home Assistant
1. Create folder in your home assistant main folder:
```bash
mkdir custom_components/media_player
```
2. Copy pykef.py and kefwireless.py into that folder. This will make the custom component kefwireless available to Home Assistant: 
```bash
cp pykef.py custom_components/media_player
cp kefwireless.py custom_components/media_player
```
3. Add component to Home Assistant by adding to configuration.yaml:
```bash
media_player:
   - platform: kefwireless
     host: 192.168.x.x # change to the IP of you speaker, no autodetection yet
     name: MyLS50W # optional, the name you want to see in Home Assistant 
     turn_on_service: switch.turn_on # optional, place a HA service to call in here: domain.service 
     turn_on_service_data: '{"entity_id": "switch.some_switch"}' # optional, place the service data in here. Must be in quotation marks ('). Must be one line   
```



## License
MIT License

## Authors
- Robin Grönberg
- Bastian Beggel
- chimpy (wireshark god)
