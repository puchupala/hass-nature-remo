"""The Nature Remo integration."""
import logging
import voluptuous as vol

from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.util import dt as dt_util

from .api import NatureRemoAPI, NatureRemoError, NatureRemoRateLimitError
from .const import (
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = DEFAULT_UPDATE_INTERVAL
PARALLEL_UPDATES = 1

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_COOL_TEMP, default=DEFAULT_COOL_TEMP): vol.Coerce(
                    int
                ),
                vol.Optional(CONF_HEAT_TEMP, default=DEFAULT_HEAT_TEMP): vol.Coerce(
                    int
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up Nature Remo component."""
    _LOGGER.debug("Setting up Nature Remo component.")
    access_token = config[DOMAIN][CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)
    api = NatureRemoAPI(access_token, session)

    async def async_update_data():
        """Fetch appliances and devices, mapping API errors for the coordinator."""
        try:
            appliances = await api.get_appliances()
            devices = await api.get_devices()
        except NatureRemoRateLimitError as err:
            # Polling again before the window resets only gets rejected.
            retry_after = None
            if err.reset is not None:
                delay = (err.reset - dt_util.utcnow()).total_seconds()
                retry_after = delay if delay > 0 else None
            raise UpdateFailed(str(err), retry_after=retry_after) from err
        except NatureRemoError as err:
            raise UpdateFailed(str(err)) from err
        return {
            "appliances": {x["id"]: x for x in appliances},
            "devices": {x["id"]: x for x in devices},
        }

    coordinator = hass.data[DOMAIN] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Nature Remo update",
        update_method=async_update_data,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )
    await coordinator.async_refresh()
    hass.data[DOMAIN] = {
        "api": api,
        "coordinator": coordinator,
        "config": config[DOMAIN],
    }

    await discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
    await discovery.async_load_platform(hass, "climate", DOMAIN, {}, config)
    return True


class NatureRemoBase(Entity):
    """Nature Remo entity base class."""

    def __init__(self, coordinator, appliance):
        self._coordinator = coordinator
        self._name = f"Nature Remo {appliance['nickname']}"
        self._appliance_id = appliance["id"]
        self._device = appliance["device"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._appliance_id

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        # Since device registration requires Config Entries, this dosen't work for now
        return {
            "identifiers": {(DOMAIN, self._device["id"])},
            "name": self._device["name"],
            "manufacturer": "Nature Remo",
            "model": self._device["serial_number"],
            "sw_version": self._device["firmware_version"],
        }


class NatureRemoDeviceBase(Entity):
    """Nature Remo Device entity base class."""

    def __init__(self, coordinator, device):
        self._coordinator = coordinator
        self._name = f"Nature Remo {device['name']}"
        self._device = device

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device["id"]

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        # The coordinator pushes updates; polling here would trigger extra API
        # requests and bypass the rate limit backoff.
        return False

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        # Since device registration requires Config Entries, this dosen't work for now
        return {
            "identifiers": {(DOMAIN, self._device["id"])},
            "name": self._device["name"],
            "manufacturer": "Nature Remo",
            "model": self._device["serial_number"],
            "sw_version": self._device["firmware_version"],
        }

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

