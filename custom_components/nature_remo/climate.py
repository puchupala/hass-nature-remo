"""Support for Nature Remo AC."""
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (ClimateEntityFeature,
                                                    HVACMode)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import NatureRemoError
from .const import (
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
)
from .coordinator import NatureRemoConfigEntry, NatureRemoCoordinator
from .entity import NatureRemoApplianceEntity

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.SWING_MODE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

MODE_HA_TO_REMO = {
    HVACMode.AUTO: "auto",
    HVACMode.FAN_ONLY: "blow",
    HVACMode.COOL: "cool",
    HVACMode.DRY: "dry",
    HVACMode.HEAT: "warm",
    HVACMode.OFF: "power-off",
}

MODE_REMO_TO_HA = {
    "auto": HVACMode.AUTO,
    "blow": HVACMode.FAN_ONLY,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "warm": HVACMode.HEAT,
    "power-off": HVACMode.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NatureRemoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nature Remo AC entities, including ones added later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        new = [
            appliance
            for appliance_id, appliance in coordinator.data["appliances"].items()
            if appliance["type"] == "AC" and appliance_id not in known
        ]
        known.update(appliance["id"] for appliance in new)
        if new:
            async_add_entities(
                NatureRemoAC(coordinator, appliance, entry.options)
                for appliance in new
            )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class NatureRemoAC(NatureRemoApplianceEntity, ClimateEntity):
    """Implementation of a Nature Remo air conditioner."""
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: NatureRemoCoordinator,
        appliance: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, appliance)
        self._default_temp = {
            HVACMode.COOL: options.get(CONF_COOL_TEMP, DEFAULT_COOL_TEMP),
            HVACMode.HEAT: options.get(CONF_HEAT_TEMP, DEFAULT_HEAT_TEMP),
        }
        self._modes = appliance["aircon"]["range"]["modes"]
        self._hvac_mode = None
        self._current_temperature = None
        self._target_temperature = None
        self._remo_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._last_target_temperature = {v: None for v in MODE_REMO_TO_HA}
        self._update(
            appliance["settings"],
            coordinator.data["devices"].get(appliance["device"]["id"]),
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        temp_range = self._current_mode_temp_range()
        if len(temp_range) == 0:
            return 0
        return min(temp_range)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        temp_range = self._current_mode_temp_range()
        if len(temp_range) == 0:
            return 0
        return max(temp_range)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.debug("Current target temperature: %s", self._target_temperature)
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        temp_range = self._current_mode_temp_range()
        if len(temp_range) >= 2:
            # determine step from the gap of first and second temperature
            step = round(temp_range[1] - temp_range[0], 1)
            if step in [1.0, 0.5]:  # valid steps
                return step
        return 1.0

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        remo_modes = list(self._modes.keys())
        ha_modes = list(map(lambda mode: MODE_REMO_TO_HA[mode], remo_modes))
        ha_modes.append(HVACMode.OFF)
        return ha_modes

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._modes[self._remo_mode]["vol"]

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self._swing_mode

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return self._modes[self._remo_mode]["dir"]

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "previous_target_temperature": self._last_target_temperature,
        }
    
    async def async_turn_off(self):
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)


    async def async_turn_on(self):
        """Turn the entity on."""
        if self._remo_mode is None:
            # if the mode is unknown, set to the default mode
            await self.async_set_hvac_mode(HVACMode.COOL)
        else:
            await self.async_set_hvac_mode(MODE_REMO_TO_HA[self._remo_mode])

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return
        if target_temp.is_integer():
            # has to cast to whole number otherwise API will return an error
            target_temp = int(target_temp)
        _LOGGER.debug("Set temperature: %d", target_temp)
        await self._post({"temperature": f"{target_temp}"})

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug("Set hvac mode: %s", hvac_mode)
        mode = MODE_HA_TO_REMO[hvac_mode]
        if mode == MODE_HA_TO_REMO[HVACMode.OFF]:
            await self._post({"button": mode})
        else:
            data = {"operation_mode": mode}
            if self._last_target_temperature[mode]:
                data["temperature"] = self._last_target_temperature[mode]
            elif self._default_temp.get(hvac_mode):
                data["temperature"] = self._default_temp[hvac_mode]
            await self._post(data)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.debug("Set fan mode: %s", fan_mode)
        await self._post({"air_volume": fan_mode})

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        _LOGGER.debug("Set swing mode: %s", swing_mode)
        await self._post({"air_direction": swing_mode})

    def _update(self, ac_settings, device=None):
        # hold this to determine the ac mode while it's turned-off
        self._remo_mode = ac_settings["mode"]
        try:
            self._target_temperature = float(ac_settings["temp"])
            self._last_target_temperature[self._remo_mode] = ac_settings["temp"]
        except:
            self._target_temperature = None

        if ac_settings["button"] == MODE_HA_TO_REMO[HVACMode.OFF]:
            self._hvac_mode = HVACMode.OFF
        else:
            self._hvac_mode = MODE_REMO_TO_HA[self._remo_mode]

        self._fan_mode = ac_settings["vol"] or None
        self._swing_mode = ac_settings["dir"] or None

        if device is not None:
            self._current_temperature = float(device["newest_events"]["te"]["val"])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply the latest data from the coordinator."""
        appliance = self.coordinator.data["appliances"].get(self._appliance_id)
        if appliance is not None:
            self._update(
                appliance["settings"],
                self.coordinator.data["devices"].get(appliance["device"]["id"]),
            )
        super()._handle_coordinator_update()

    async def _post(self, data):
        try:
            response = await self.coordinator.api.set_aircon_settings(
                self._appliance_id, data
            )
        except NatureRemoError as err:
            raise HomeAssistantError(
                f"Failed to update air conditioner settings: {err}"
            ) from err
        self._update(response)
        self.async_write_ha_state()

    def _current_mode_temp_range(self):
        temp_range = self._modes[self._remo_mode]["temp"]
        return list(map(float, filter(None, temp_range)))
