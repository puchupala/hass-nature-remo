"""Support for Nature Remo TV."""
import logging
import asyncio

from homeassistant.const import (
    STATE_ON,
)
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    DEVICE_CLASS_TV,
    STATE_OFF,
)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from . import DOMAIN, NatureRemoBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Nature Remo TV."""
    if discovery_info is None:
        return
    _LOGGER.debug("Setting up sensor platform.")
    coordinator = hass.data[DOMAIN]["coordinator"]
    api = hass.data[DOMAIN]["api"]
    appliances = coordinator.data["appliances"]
    async_add_entities(
        [
            NatureRemoTV(coordinator, api, appliance)
            for appliance in appliances.values()
            if appliance["type"] == "TV"
        ]
    )


class NatureRemoTV(NatureRemoBase, MediaPlayerEntity):
    """Implementation of a Nature Remo TV."""

    SOURCES = {
        "t": "Terrestrial",
        "bs": "BS",
        "cs": "CS",
    }

    def __init__(self, coordinator, api, appliance):
        super().__init__(coordinator, appliance)
        self._api = api
        self._sources = self._detect_sources(appliance)
        self._supported_features = self._detect_supported_features(appliance, self._sources)
        self._transition = asyncio.Lock()
        self._state = STATE_OFF
        self._is_volume_muted = False
        self._source = None
        try:
            self._source = self.SOURCES[appliance["tv"]["state"]["input"]]
        except KeyError:
            pass

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._sources.keys())

    @property
    def state(self):
        """Return the current state of media player."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._is_volume_muted

    @property
    def assumed_state(self):
        return True

    @property
    def supported_features(self):
        return self._supported_features

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return None

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TV

    async def async_turn_on(self):
        """Turn the media player on."""
        async with self._transition:
            if self._state == STATE_OFF:
                await self._signal("power")
                self._state = STATE_ON
                self.async_write_ha_state()
    
    async def async_turn_off(self):
        """Turn the media player off."""
        async with self._transition:
            if self._state == STATE_ON:
                await self._signal("power")
                self._state = STATE_OFF
                self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        async with self._transition:
            await self._signal("mute")
            self._is_volume_muted = not self._is_volume_muted
            self.async_write_ha_state()

    async def async_media_play(self):
        """Send play command."""
        await self._signal("play")

    async def async_media_pause(self):
        """Send pause command."""
        await self._signal("pause")

    async def async_media_stop(self):
        """Send stop command."""
        await self._signal("stop")

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._signal("prev")

    async def async_media_next_track(self):
        """Send next track command."""
        await self._signal("next")

    async def async_select_source(self, source):
        """Select input source."""
        async with self._transition:
            await self._signal(self._sources[source])
            self._source = source
            self.async_write_ha_state()

    async def async_volume_up(self):
        """Turn volume up for media player."""
        await self._signal("vol-up")

    async def async_volume_down(self):
        """Turn volume down for media player."""
        await self._signal("vol-down")

    # Private methods

    def _detect_supported_features(self, appliance, sources):
        supported_features = 0
        buttons = [b["name"] for b in appliance["tv"]["buttons"]]
        if sources is not {}:
            supported_features |= SUPPORT_SELECT_SOURCE
        if "power" in buttons:
            supported_features |= SUPPORT_TURN_ON
            supported_features |= SUPPORT_TURN_OFF
        if "next" in buttons:
            supported_features |= SUPPORT_NEXT_TRACK
        if "prev" in buttons:
            supported_features |= SUPPORT_PREVIOUS_TRACK
        if "pause" in buttons:
            supported_features |= SUPPORT_PAUSE
        if "play" in buttons:
            supported_features |= SUPPORT_PLAY
        if "stop" in buttons:
            supported_features |= SUPPORT_STOP
        if "mute" in buttons:
            supported_features |= SUPPORT_VOLUME_MUTE
        if ("vol-up" in buttons) and ("vol-down" in buttons):
            supported_features |= SUPPORT_VOLUME_STEP
        return supported_features

    def _detect_sources(self, appliance):
        """
        return: {"source_name": "button_name", "source_name": "button_name", ...}
        """
        sources = {}
        for button in appliance["tv"]["buttons"]:
            if button["name"] == "input-terrestrial":
                sources["Terrestrial"] = "input-terrestrial"
            elif button["name"] == "input-bs":
                sources["BS"] = "input-bs"
            elif button["name"] == "input-cs":
                sources["CS"] = "input-cs"
            elif button["name"] == "select-input-src":
                sources["Input"] = "select-input-src"
        return sources

    async def _signal(self, button_name):
        response = await self._api.post(f"/appliances/{self._appliance_id}/tv", {"button": button_name})
