# 🎵 Asyncio Python API for KEF Speakers 🎵

[![license](https://img.shields.io/github/license/basnijholt/aiokef)](https://github.com/basnijholt/aiokef/blob/master/LICENSE)
[![tests](https://github.com/basnijholt/aiokef/workflows/tests/badge.svg)](https://github.com/basnijholt/aiokef/actions?query=workflow%3Atests)
[![codecov](https://img.shields.io/codecov/c/github/basnijholt/aiokef)](https://codecov.io/gh/basnijholt/aiokef)
[![docs](https://img.shields.io/readthedocs/aiokef)](https://aiokef.readthedocs.io)
[![version](https://img.shields.io/pypi/v/aiokef)](https://pypi.org/project/aiokef/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aiokef)](https://pypi.org/project/aiokef/)

Supported: *KEF LS50 Wireless* (tested with latest firmware of 19-11-2019: p6.3001902221.105039422 and older firmware: p6.2101809171.105039422) 📶

Untested: *KEF LSX* ❓

## 🚀 Supported Features
- Get and set volume 🔊
- Mute and unmute 🤫
- Get and set source input 🔄
- Turn speaker on and off 🔌
- Invert L/R to R/L 🔄
- Play and pause (only works with Wifi and Bluetooth) ⏯️
- Previous and next track (only works with Wifi and Bluetooth) ⏮️⏭️
- Set the standby time to infinite, 20 minutes, or 60 minutes ⏱️
- Automatically connects and disconnects when speakers goes online/offline 🌐
- Control **all** DSP settings! 🎛️

## 🏠 Use in Home Assistant
See [home-assistant.io/integrations/kef](https://www.home-assistant.io/integrations/kef/).

## 💻 Install
```bash
pip install aiokef
```

## 🗣️ Discussion
Check out this [Home Assistant discussion thread](https://community.home-assistant.io/t/kef-ls50-wireless/) to join the conversation on the creation of the KEF speakers.

## 📄 License
MIT License

## 👥 Contributions
- Bas Nijholt 🚀
- Robin Grönberg ([@Gronis](https://github.com/Gronis/pykef))
- Bastian Beggel ([@bastianbeggel](https://github.com/bastianbeggel/hasskef))
- chimpy ([@chimpy](https://github.com/chimpy))
