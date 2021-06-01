"""Support for Nature Remo Light."""
import logging
import asyncio

from homeassistant.components.light import (
    LightEntity,
    COLOR_MODE_ONOFF,
)
from . import DOMAIN, NatureRemoBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Nature Remo Light."""
    if discovery_info is None:
        return
    _LOGGER.debug("Setting up light platform.")
    coordinator = hass.data[DOMAIN]["coordinator"]
    config = hass.data[DOMAIN]["config"]
    appliances = coordinator.data["appliances"]
    async_add_entities(
        [
            NatureRemoToggleLight(hass.data[DOMAIN], appliance)
            for appliance in appliances.values()
            if (appliance["type"] == "IR") and (appliance["nickname"].strip().lower() == config["togglelight_name"].strip().lower())
        ]
    )


class NatureRemoToggleLight(NatureRemoBase, LightEntity):
    """Implementation of a Nature Remo Toggle Light component."""

    def __init__(self, data, appliance):
        super().__init__(data["coordinator"], appliance)
        self._is_on = True  # The light is more likely to be ON so let's default to ON
        self._api = data["api"]
        self._delay = data["config"]["togglelight_delay"] / 1000.0  # Convert from ms to s
        self._transition = asyncio.Lock()

        self._signal_id = None
        button_name = data["config"]["togglelight_button"].strip().lower()
        for signal in appliance["signals"]:
            if signal["name"] == button_name:
                self._signal_id = signal["id"]
        if self._signal_id is None:
            raise Exception("Light {} does not have button {}".format(appliance["nickname"], button_name))
        

    # Entity methods

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        # Remo does return light.state however it doesn't seem to be correct
        # in my experience.
        return True

    # ToggleEntity methods

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._is_on

    @property
    def color_mode(self):
        """Return True if entity is on."""
        return COLOR_MODE_ONOFF

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        async with self._transition:
            if not self._is_on:
                await self._api.post(f"/signals/{self._signal_id}/send", None)
                self._is_on = True
                self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        async with self._transition:
            if self._is_on:
                await self._api.post(f"/signals/{self._signal_id}/send", None)
                await asyncio.sleep(self._delay)
                await self._api.post(f"/signals/{self._signal_id}/send", None)
                self._is_on = False
                self.async_write_ha_state()
