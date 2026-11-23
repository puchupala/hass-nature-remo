"""Support for Nature Remo sensors."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NatureRemoConfigEntry, NatureRemoCoordinator
from .entity import NatureRemoApplianceEntity, NatureRemoDeviceEntity

APPLIANCE_TYPE_SMART_METER = "EL_SMART_METER"
# ECHONET Lite property holding the measured instantaneous power, in watts.
EPC_MEASURED_INSTANTANEOUS = 231

# One sensor per event the Remo reports. The key is the API's event name and
# is part of the unique ID.
DEVICE_SENSORS = (
    SensorEntityDescription(
        key="te",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hu",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="il",
        name="Illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NatureRemoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nature Remo sensors, including ones added later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        entities: list[SensorEntity] = [
            NatureRemoPowerSensor(coordinator, appliance)
            for appliance in coordinator.data["appliances"].values()
            if appliance["type"] == APPLIANCE_TYPE_SMART_METER
        ]
        entities.extend(
            NatureRemoDeviceSensor(coordinator, device, description)
            for device in coordinator.data["devices"].values()
            for description in DEVICE_SENSORS
            if description.key in device.get("newest_events", {})
        )
        new = [entity for entity in entities if entity.unique_id not in known]
        known.update(entity.unique_id for entity in new)
        if new:
            async_add_entities(new)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class NatureRemoPowerSensor(NatureRemoApplianceEntity, SensorEntity):
    """The power currently measured by a smart meter (Nature Remo E)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the measured instantaneous power."""
        properties = (self.appliance.get("smart_meter") or {}).get(
            "echonetlite_properties"
        ) or []
        for echonet_property in properties:
            if echonet_property.get("epc") == EPC_MEASURED_INSTANTANEOUS:
                try:
                    return int(echonet_property["val"])
                except (KeyError, TypeError, ValueError):
                    return None
        return None


class NatureRemoDeviceSensor(NatureRemoDeviceEntity, SensorEntity):
    """A sensor built into a Nature Remo."""

    def __init__(
        self,
        coordinator: NatureRemoCoordinator,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize from the device as returned by the API."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device['id']}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the latest value the Remo reported."""
        event = self.device.get("newest_events", {}).get(self.entity_description.key)
        return event.get("val") if event else None
