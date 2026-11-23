# Home Assistant integration for Nature Remo

A custom [Home Assistant](https://www.home-assistant.io) integration for
[Nature Remo](https://en.nature.global/en/) with **air conditioner control**, plus the Remo's
built-in sensors and smart meter power.

⚠️ This integration is neither Nature official nor Home Assistant official. **Use at your own risk.** ⚠️

<img src="./assets/screenshot_1.png" width="600"><img src="./assets/screenshot_2.png" width="200">

## Why this integration

Home Assistant 2026.11 and later ships a built-in Nature Remo integration, but it only provides
sensors. This one adds a climate entity for air conditioners.

Both use the `nature_remo` domain, so they cannot run side by side: **while this integration is
installed it replaces the built-in one.** To switch to the built-in integration, delete the
Nature Remo entry under **Settings** > **Devices & services** first, then uninstall this
integration, restart, and add Nature Remo again. The two store their configuration differently,
so the entry cannot be carried over.

## Features

| | Supported |
|---|---|
| Air conditioner | Mode (auto, cool, heat, dry, fan only, off), target temperature, fan mode, swing mode, turn on/off, room temperature from the Remo |
| Remo sensors | Temperature, humidity, illuminance |
| Smart meter (Nature Remo E / E lite) | Current power usage |
| Lights, TVs, other IR signals, motion sensor | Not supported |

Air conditioner details:

- The available temperatures, fan modes and swing modes follow what the selected mode of your AC
  supports. Modes without a temperature setting (such as fan only) do not offer one.
- The last target temperature of each mode is remembered and restored when you switch back to
  that mode. The remembered values are exposed in the `previous_target_temperature` attribute.
- The first time a mode is used, cooling and heating start from a default temperature that you
  can configure (28 °C and 20 °C unless changed).

Illuminance is the Remo's own reading, shown in lx as reported by the Nature API.

## Requirements

- Home Assistant 2026.11 or later (tested on Home Assistant Core 2026.11.2, Home Assistant OS)
- A Nature account with an access token from https://home.nature.global

## Installation

### Marketplace (recommended)

1. Go to **Settings** > **Marketplace**
1. Select **Add from link** in the upper-right corner
1. Enter `puchupala/hass-nature-remo` and select **Add** (choose **Integration** if asked for a
   type, and confirm if asked about replacing the built-in Nature Remo integration)
1. Select **Install**, then restart Home Assistant

Updates are offered in the Marketplace and through the `update.nature_remo` entity.

### Manual

1. Download the [latest release](https://github.com/puchupala/hass-nature-remo/releases/latest)
1. Copy the `custom_components/nature_remo` folder into the `custom_components` folder of your
   Home Assistant config directory
1. Restart Home Assistant

## Configuration

1. Go to https://home.nature.global, sign in and generate an access token
1. In Home Assistant, go to **Settings** > **Devices & services** > **Add integration** and
   select **Nature Remo**
1. Enter the access token

Each Nature account can be added once. Appliances and Remos added to the account later show up
by themselves within a minute; no restart is needed.

### Options

Select **Configure** on the integration to change the default cooling and heating temperatures.

### Replacing the access token

If the Nature API rejects the token, Home Assistant asks you to reauthenticate. Enter a new token
for the same Nature account.

## Devices and entities

| Device | Entities |
|---|---|
| `Nature Remo <Remo name>` — the Remo itself | `sensor.nature_remo_<remo name>_temperature`, `…_humidity`, `…_illuminance` (only those the Remo reports) |
| `Nature Remo <appliance nickname>` — an air conditioner, linked to its Remo | `climate.nature_remo_<appliance nickname>` |
| `Nature Remo <appliance nickname>` — a smart meter, linked to its Remo | `sensor.nature_remo_<appliance nickname>` (power, W) |

The climate and smart meter entities are the main entity of their device, so their area is set on
the **device**, not on the entity.

## Migrating from YAML (0.6 and earlier)

Configuration through `configuration.yaml` is no longer used. A block like the one below is
imported automatically the first time Home Assistant starts with 0.7.0 or later, including
`cool_temperature` and `heat_temperature` if you had set them.

```yaml
nature_remo:
  access_token: YOUR_ACCESS_TOKEN
```

- Entities keep their entity IDs and names, so automations, dashboards and voice assistant
  exposure keep working.
- A repair notice asks you to remove the block afterwards. Remove it and restart.
- An area assigned to the air conditioner entity has to be set again on its new device.

## How it talks to the Nature API

- Polling: once every 60 seconds, two requests per cycle. The Nature API allows 30 requests per
  5 minutes for the whole account, and every command sent to an AC also counts.
- When the API reports that the rate limit is exceeded, polling pauses until the limit resets.
- While the API cannot be reached, entities become unavailable instead of showing old values, and
  recover on their own. If it is unreachable when Home Assistant starts, setup is retried
  automatically.
- A command the API rejects is shown as an error in Home Assistant and leaves the entity state
  unchanged.

## Troubleshooting

Enable debug logging in `configuration.yaml` and restart:

```yaml
logger:
  logs:
    custom_components.nature_remo: debug
```

Please report problems at https://github.com/puchupala/hass-nature-remo/issues.

## Development

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/python -m pytest
```

Tests run against the Home Assistant version pinned in `requirements_test.txt`, with the Nature
API mocked. GitHub Actions runs the tests and
[hassfest](https://github.com/home-assistant/actions#hassfest) on every push; hassfest reports
one expected warning because the domain is shared with the built-in integration.

Work happens on topic branches that are merged into `develop`. The Marketplace installs the
latest GitHub release, so a new version is published by bumping `version` in
`custom_components/nature_remo/manifest.json` and creating a release tagged `v<version>` from
`develop`.

## Credits

Originally written by [Yuto Yazaki](https://github.com/yutoyazaki/hass-nature-remo), with
Home Assistant compatibility updates from [doenau](https://github.com/doenau/hass-nature-remo).
Licensed under the [MIT License](./LICENSE).
