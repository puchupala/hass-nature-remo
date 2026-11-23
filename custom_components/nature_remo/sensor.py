"""Support for Nature Remo sensors."""
import logging

from homeassistant.const import (
    UnitOfPower,
    PERCENTAGE,
    LIGHT_LUX,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_system import UnitOfTemperature
from homeassistant.components.sensor.const import SensorDeviceClass

from .coordinator import NatureRemoConfigEntry
from .entity import NatureRemoApplianceEntity, NatureRemoDeviceEntity

_LOGGER = logging.getLogger(__name__)


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
        entities = [
            NatureRemoE(coordinator, appliance)
            for appliance in coordinator.data["appliances"].values()
            if appliance["type"] == "EL_SMART_METER"
        ]
        for device in coordinator.data["devices"].values():
            for event in device["newest_events"]:
                if sensor_class := DEVICE_SENSORS.get(event):
                    entities.append(sensor_class(coordinator, device))
        new = [entity for entity in entities if entity.unique_id not in known]
        known.update(entity.unique_id for entity in new)
        if new:
            async_add_entities(new)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class NatureRemoE(NatureRemoApplianceEntity):
    """Implementation of a Nature Remo E sensor."""

    def __init__(self, coordinator, appliance):
        super().__init__(coordinator, appliance)
        self._unit_of_measurement = UnitOfPower.WATT

    @property
    def state(self):
        """Return the state of the sensor."""
        smart_meter = self.appliance["smart_meter"]
        echonetlite_properties = smart_meter["echonetlite_properties"]
        measured_instantaneous = next(
            value["val"] for value in echonetlite_properties if value["epc"] == 231
        )
        _LOGGER.debug("Current state: %sW", measured_instantaneous)
        return measured_instantaneous

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UnitOfPower.WATT

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.power


class NatureRemoTemperatureSensor(NatureRemoDeviceEntity):
    """Implementation of a Nature Remo sensor."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device['id']}-te"
        self._attr_name = "Temperature"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UnitOfTemperature.CELSIUS

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device["newest_events"]["te"]["val"]

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.TEMPERATURE


class NatureRemoHumiditySensor(NatureRemoDeviceEntity):
    """Implementation of a Nature Remo sensor."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device['id']}-hu"
        self._attr_name = "Humidity"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return PERCENTAGE

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device["newest_events"]["hu"]["val"]

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.HUMIDITY


class NatureRemoIlluminanceSensor(NatureRemoDeviceEntity):
    """Implementation of a Nature Remo sensor."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device['id']}-il"
        self._attr_name = "Illuminance"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return LIGHT_LUX

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device["newest_events"]["il"]["val"]

    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.ILLUMINANCE


DEVICE_SENSORS = {
    "te": NatureRemoTemperatureSensor,
    "hu": NatureRemoHumiditySensor,
    "il": NatureRemoIlluminanceSensor,
}
