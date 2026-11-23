# Home Assistant integration for Nature Remo

Yet another [Home Assistant](https://www.home-assistant.io) component for [Nature Remo](https://en.nature.global/en/).

⚠️This integration is neither Nature Remo official nor Home Assistant official. **Use at your own risk.** ⚠️

<img src="./assets/screenshot_1.png" width="600"><img src="./assets/screenshot_2.png" width="200">

## Supported features

- [x] Air Conditionar
  - [x] Set mode (e.g. cool, warm, blow etc.)
  - [x] Set temperature
  - [x] Set fan mode
  - [x] Set swing mode
  - [x] Show current temperature
  - [x] Remember previous target temperatures when switching modes back and forth
- [x] Energy Sensor (Nature Remo E/E Lite)
  - [x] Fetch current power usage
- [ ] Switch
- [ ] Light
- [ ] TV
- [X] Others
  - [X] Fetch sensor data

Tested on Home Assistant Core 2026.11.2 on Home Assistant OS

## Installation

### Install via Marketplace (recommended)

Requires Home Assistant 2026.11 or later.

1. Go to **Settings** > **Marketplace**
1. Select **Add from link** in the upper-right corner
1. Enter `puchupala/hass-nature-remo` and select **Add** (choose **Integration** if asked for a type)
1. Select **Install**, then restart Home Assistant

### Manual Install

1. Download this repository
1. Copy the `custom_components/nature_remo` folder into the `custom_components` folder of your config directory

```
{path_to_your_config}
├── configuration.yaml
└── custom_components
    └── nature_remo
        ├── __init__.py
        ├── climate.py
        ├── manifest.json
        └── sensor.py
```

## Configuration

1. Go to https://home.nature.global and sign in/up
1. Generate access token
1. Add following codes to your `configuration.yaml` file

```yaml
nature_remo:
  access_token: YOUR_ACCESS_TOKEN
```
