# Python interface to control KEF speakers
Supported: KEF LS50 Wireless (Requires [firmware](http://international.kef.com/product-support) June 2018 or later)

Untested: KEF LSX

## Supported features
- Get and set volume
- Mute and Unmute
- Get and set source input
- Get if the speakers are online
- Automatically connects and disconnects when speakers goes online/offline
- Turn off speaker
- Turn on speaker (via HA service call)

## Notes
- Turning on is impossible over TCP/IP because the speaker turns off network interface when turned off. This is true for LS50 Wireless. The LSX should be possible to turn on.
- LS50 Wireless take about 20s to boot.

## Discussion
See [home assistant thread](https://community.home-assistant.io/t/kef-ls50-wireless/)

## Use in Home Assistant
1. Create folder in your home assistant `config` folder:
```bash
mkdir /path/to/config/custom_components/
cp -r custom_components/kef /path/to/config/custom_components/
```
2. Add component to Home Assistant by adding to `configuration.yaml`:
```bash
media_player:
   - platform: kefwireless
     host: 192.168.x.x # change to the IP of you speaker, no autodetection yet
     name: MyLS50W # optional, the name you want to see in Home Assistant
     turn_on_service: switch.turn_on # optional, place a HA service to call in here: domain.service
     turn_on_data: '{"entity_id": "switch.some_switch"}' # optional, place the service data in here. Must be in quotation marks ('). Must be one line
```

## License
MIT License

## Authors
- Bas Nijholt
- Robin Grönberg
- Bastian Beggel
- chimpy (wireshark god)
