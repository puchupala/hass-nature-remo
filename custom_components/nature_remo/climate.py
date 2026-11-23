"""Support for air conditioners controlled through Nature Remo."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
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

APPLIANCE_TYPE_AC = "AC"
BUTTON_POWER_OFF = "power-off"

MODE_HA_TO_REMO = {
    HVACMode.AUTO: "auto",
    HVACMode.FAN_ONLY: "blow",
    HVACMode.COOL: "cool",
    HVACMode.DRY: "dry",
    HVACMode.HEAT: "warm",
}
MODE_REMO_TO_HA = {remo: ha for ha, remo in MODE_HA_TO_REMO.items()}

VALID_TEMPERATURE_STEPS = (1.0, 0.5)
DEFAULT_TEMPERATURE_STEP = 1.0


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
            if appliance["type"] == APPLIANCE_TYPE_AC and appliance_id not in known
        ]
        known.update(appliance["id"] for appliance in new)
        if new:
            async_add_entities(
                NatureRemoAC(coordinator, appliance, entry.options)
                for appliance in new
            )

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


def _values(mode_range: Mapping[str, Any], key: str) -> list[str]:
    """Return the selectable values of a mode, without the empty placeholder."""
    return [value for value in mode_range.get(key) or [] if value]


class NatureRemoAC(NatureRemoApplianceEntity, ClimateEntity):
    """An air conditioner controlled through a Nature Remo."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: NatureRemoCoordinator,
        appliance: dict[str, Any],
        options: Mapping[str, Any],
    ) -> None:
        """Initialize from the appliance as returned by the API."""
        super().__init__(coordinator, appliance)
        self._default_temp = {
            HVACMode.COOL: options.get(CONF_COOL_TEMP, DEFAULT_COOL_TEMP),
            HVACMode.HEAT: options.get(CONF_HEAT_TEMP, DEFAULT_HEAT_TEMP),
        }
        self._modes: dict[str, dict[str, Any]] = appliance["aircon"]["range"]["modes"]
        self._attr_hvac_modes = [
            MODE_REMO_TO_HA[mode] for mode in self._modes if mode in MODE_REMO_TO_HA
        ] + [HVACMode.OFF]
        # The Remo mode stays known while the AC is off, to turn it back on.
        self._remo_mode: str | None = None
        # Last target temperature per Remo mode, restored when switching back.
        self._last_target_temperature: dict[str, str | None] = dict.fromkeys(
            MODE_REMO_TO_HA
        )
        self._apply_settings(appliance["settings"])
        self._apply_device(coordinator.data["devices"].get(appliance["device"]["id"]))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the remembered target temperature of each mode."""
        return {"previous_target_temperature": dict(self._last_target_temperature)}

    async def async_turn_on(self) -> None:
        """Turn on in the mode the AC was last in."""
        await self.async_set_hvac_mode(
            MODE_REMO_TO_HA.get(self._remo_mode, HVACMode.COOL)
        )

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (target_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        # The API rejects whole numbers written with a decimal point.
        if float(target_temp).is_integer():
            target_temp = int(target_temp)
        await self._async_send({"temperature": str(target_temp)})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new operation mode, restoring that mode's last temperature."""
        if hvac_mode == HVACMode.OFF:
            await self._async_send({"button": BUTTON_POWER_OFF})
            return
        mode = MODE_HA_TO_REMO[hvac_mode]
        data = {"operation_mode": mode}
        if temperature := self._last_target_temperature.get(mode):
            data["temperature"] = temperature
        elif temperature := self._default_temp.get(hvac_mode):
            data["temperature"] = str(temperature)
        await self._async_send(data)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode."""
        await self._async_send({"air_volume": fan_mode})

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set a new swing mode."""
        await self._async_send({"air_direction": swing_mode})

    async def _async_send(self, data: dict[str, str]) -> None:
        """Send settings to the AC and apply the settings the API reports back."""
        try:
            settings = await self.coordinator.api.set_aircon_settings(
                self._appliance_id, data
            )
        except NatureRemoError as err:
            raise HomeAssistantError(
                f"Failed to update air conditioner settings: {err}"
            ) from err
        self._apply_settings(settings)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply the latest data from the coordinator."""
        appliance = self.coordinator.data["appliances"].get(self._appliance_id)
        if appliance is not None:
            self._apply_settings(appliance["settings"])
            self._apply_device(
                self.coordinator.data["devices"].get(appliance["device"]["id"])
            )
        super()._handle_coordinator_update()

    def _apply_device(self, device: dict[str, Any] | None) -> None:
        """Take the room temperature from the Remo, if it has such a sensor."""
        try:
            self._attr_native_current_temperature = float(
                device["newest_events"]["te"]["val"]  # type: ignore[index]
            )
        except (KeyError, TypeError, ValueError):
            self._attr_native_current_temperature = None

    def _apply_settings(self, settings: Mapping[str, Any]) -> None:
        """Update the entity state from air conditioner settings."""
        self._remo_mode = mode = settings["mode"]
        mode_range = self._modes.get(mode, {})

        try:
            self._attr_native_target_temperature = float(settings["temp"])
        except (KeyError, TypeError, ValueError):
            # Modes such as fan-only and dry have no temperature setting.
            self._attr_native_target_temperature = None
        else:
            self._last_target_temperature[mode] = settings["temp"]

        if settings.get("button") == BUTTON_POWER_OFF:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = MODE_REMO_TO_HA.get(mode)

        self._attr_fan_mode = settings.get("vol") or None
        self._attr_fan_modes = _values(mode_range, "vol")
        self._attr_swing_mode = settings.get("dir") or None
        self._attr_swing_modes = _values(mode_range, "dir")

        # Only offer what the current mode can actually set.
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self._attr_fan_modes:
            features |= ClimateEntityFeature.FAN_MODE
        if self._attr_swing_modes:
            features |= ClimateEntityFeature.SWING_MODE

        temperatures = sorted(float(value) for value in _values(mode_range, "temp"))
        if temperatures:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_min_temp = temperatures[0]
            self._attr_max_temp = temperatures[-1]
        else:
            # No temperature setting in this mode: report the standard range
            # instead of an empty one.
            self._attr_min_temp = DEFAULT_MIN_TEMP
            self._attr_max_temp = DEFAULT_MAX_TEMP
        self._attr_target_temperature_step = DEFAULT_TEMPERATURE_STEP
        if len(temperatures) >= 2:
            step = round(temperatures[1] - temperatures[0], 1)
            if step in VALID_TEMPERATURE_STEPS:
                self._attr_target_temperature_step = step
        self._attr_supported_features = features
