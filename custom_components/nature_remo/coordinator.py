"""Data update coordinator for the Nature Remo integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    NatureRemoAPI,
    NatureRemoAuthError,
    NatureRemoError,
    NatureRemoRateLimitError,
)
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type NatureRemoConfigEntry = ConfigEntry[NatureRemoCoordinator]
# {"appliances": {appliance id: appliance}, "devices": {device id: device}}
type NatureRemoData = dict[str, dict[str, dict[str, Any]]]


class NatureRemoCoordinator(DataUpdateCoordinator[NatureRemoData]):
    """Poll appliances and devices; the only source of API read requests."""

    config_entry: NatureRemoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NatureRemoConfigEntry,
        api: NatureRemoAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> NatureRemoData:
        """Fetch appliances and devices, mapping API errors for Home Assistant."""
        try:
            appliances = await self.api.get_appliances()
            devices = await self.api.get_devices()
        except NatureRemoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
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
            "appliances": {appliance["id"]: appliance for appliance in appliances},
            "devices": {device["id"]: device for device in devices},
        }
