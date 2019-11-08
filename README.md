# Python interface to control KEF speakers
Supported: KEF LS50 Wireless (Requires [firmware](http://international.kef.com/product-support) June 2018 or later)

Untested: KEF LSX

## Supported features
- Get and set volume
- Mute and unmute
- Get and set source input
- Automatically connects and disconnects when speakers goes online/offline
- Turn speaker on and off


## Discussion
See this [Home Assistant discussion thread](https://community.home-assistant.io/t/kef-ls50-wireless/).

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
     host: 192.168.x.x  # the IP of your speaker
     name: MyAwesomeSpeaker  # optional, the name in Home Assistant
     maximum_volume: 0.5  # optional, to avoid extremely loud volumes
     volume_step: 0.05  # optional
```

## License
MIT License

## Authors
- Bas Nijholt
- Robin Grönberg ([@Gronis](https://github.com/Gronis/pykef))
- Bastian Beggel ([@bastianbeggel](https://github.com/bastianbeggel/hasskef))
- chimpy ([@chimpy](https://github.com/chimpy))
