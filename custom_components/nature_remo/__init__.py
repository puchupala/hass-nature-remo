"""The Nature Remo integration."""

import logging
from typing import Any

import probatio

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import NatureRemoAPI
from .const import (
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    DOMAIN,
)
from .coordinator import NatureRemoConfigEntry, NatureRemoCoordinator
from .entity import remo_device_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

# YAML configuration is deprecated: it is only read to import it into a config entry.
CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_ACCESS_TOKEN): cv.string,
                probatio.Optional(
                    CONF_COOL_TEMP, default=DEFAULT_COOL_TEMP
                ): probatio.Coerce(int),
                probatio.Optional(
                    CONF_HEAT_TEMP, default=DEFAULT_HEAT_TEMP
                ): probatio.Coerce(int),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the YAML configuration, if there is any."""
    if DOMAIN in config:
        hass.async_create_task(_async_import_yaml(hass, dict(config[DOMAIN])))
    return True


async def _async_import_yaml(hass: HomeAssistant, conf: dict[str, Any]) -> None:
    """Turn the YAML configuration into a config entry and tell the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") == "invalid_auth"
    ):
        issue = "yaml_import_invalid_auth"
    else:
        # Imported now, or already imported on an earlier start.
        issue = "deprecated_yaml"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue,
    )


async def async_setup_entry(hass: HomeAssistant, entry: NatureRemoConfigEntry) -> bool:
    """Set up Nature Remo from a config entry."""
    api = NatureRemoAPI(entry.data[CONF_ACCESS_TOKEN], async_get_clientsession(hass))
    coordinator = NatureRemoCoordinator(hass, entry, api)
    # Raises ConfigEntryNotReady on failure, so Home Assistant retries the setup.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the Remo devices first so that appliances can be linked to them.
    device_registry = dr.async_get(hass)
    for device in coordinator.data["devices"].values():
        device_registry.async_get_or_create_from_info(
            config_entry_id=entry.entry_id, device_info=remo_device_info(device)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NatureRemoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
