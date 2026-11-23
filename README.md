# Home Assistant integration for Nature Remo

Yet another [Home Assistant](https://www.home-assistant.io) component for [Nature Remo](https://en.nature.global/en/).

⚠️This integration is neither Nature Remo official nor Home Assistant official. **Use at your own risk.** ⚠️

<img src="./assets/screenshot_1.png" width="600"><img src="./assets/screenshot_2.png" width="200">

## Supported features

- [x] Air Conditioner
  - [x] Set mode (e.g. cool, warm, blow etc.)
  - [x] Set temperature
  - [x] Set fan mode
  - [x] Set swing mode
  - [x] Show current temperature
  - [x] Remember previous target temperatures when switching modes back and forth
- [x] Energy Sensor (Nature Remo E/E Lite)
  - [x] Fetch current power usage
- [x] Remo sensors
  - [x] Temperature, humidity and illuminance
- [ ] Switch
- [ ] Light
- [ ] TV

Requires Home Assistant 2026.11 or later. Tested on Home Assistant Core 2026.11.2 on Home Assistant OS.

Home Assistant also ships a built-in Nature Remo integration (sensors only). This custom
integration uses the same domain and replaces it while installed.

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


## Configuration

1. Go to https://home.nature.global and sign in/up
1. Generate an access token
1. In Home Assistant, go to **Settings** > **Devices & services** > **Add integration**, select **Nature Remo** and enter the access token

The default target temperatures used when switching to cooling or heating for the first
time can be changed with **Configure** on the integration.

### Migrating from YAML

Configuration through `configuration.yaml` is no longer used. An existing block like the one
below is imported automatically the first time Home Assistant starts with this version;
entities keep their entity IDs. Remove the block afterwards.

```yaml
nature_remo:
  access_token: YOUR_ACCESS_TOKEN
```

## Development

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/python -m pytest
```
