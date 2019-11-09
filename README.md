# Home Assistant `custom_component` for KEF speakers
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

Supported: *KEF LS50 Wireless (tested with latest firmware at 08-11-2019)*
Untested: *KEF LSX*

## Supported features
- Get and set volume
- Mute and unmute
- Get and set source input
- Turn speaker on and off
- Automatically connects and disconnects when speakers goes online/offline

## Use in Home Assistant

### Install
*Installation with [HACS](https://hacs.xyz/)*
Go to the [HACS](https://hacs.xyz/) store and install KEF.

*Manual installation*
Create folder in your home assistant `config` folder:
```bash
mkdir -p /path/to/config/custom_components/
cp -r custom_components/kef /path/to/config/custom_components/
```

### Configure
Add the component to Home Assistant by adding the following to `configuration.yaml`:
```bash
media_player:
   - platform: kef
     host: 192.168.x.x  # the IP of your speaker
     name: MyAwesomeSpeaker  # optional, the name in Home Assistant
     maximum_volume: 0.5  # optional, to avoid extremely loud volumes
     volume_step: 0.05  # optional
```

## Discussion
See this [Home Assistant discussion thread](https://community.home-assistant.io/t/kef-ls50-wireless/) where the creation of the KEF speakers is discussed.

## License
MIT License

## Contributions
- Bas Nijholt
- Robin Grönberg ([@Gronis](https://github.com/Gronis/pykef))
- Bastian Beggel ([@bastianbeggel](https://github.com/bastianbeggel/hasskef))
- chimpy ([@chimpy](https://github.com/chimpy))
