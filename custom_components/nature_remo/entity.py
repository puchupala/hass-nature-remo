"""Base entities for the Nature Remo integration."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NatureRemoCoordinator

# Entities are named after their device. The device names carry this prefix so
# that the resulting entity names and entity IDs match the ones this
# integration has always used ("Nature Remo <name>").
NAME_PREFIX = "Nature Remo"


def remo_device_info(device: dict[str, Any]) -> DeviceInfo:
    """Build device registry info for a Nature Remo hardware device."""
    # firmware_version looks like "Remo/1.14.6": product name, then version.
    model, _, sw_version = (device.get("firmware_version") or "").partition("/")
    return DeviceInfo(
        identifiers={(DOMAIN, device["id"])},
        name=f"{NAME_PREFIX} {device['name']}".strip(),
        manufacturer="Nature",
        model=model or None,
        sw_version=sw_version or None,
        serial_number=device.get("serial_number"),
    )


def appliance_device_info(
    hass: HomeAssistant, config_entry_id: str, appliance: dict[str, Any]
) -> DeviceInfo:
    """Build device registry info for an appliance controlled through a Remo."""
    model = appliance.get("model") or {}
    device_info = DeviceInfo(
        identifiers={(DOMAIN, appliance["id"])},
        name=f"{NAME_PREFIX} {appliance['nickname']}".strip(),
        manufacturer=model.get("manufacturer") or None,
        model=model.get("name") or None,
    )
    # Link the appliance to its Remo, which setup has already registered.
    remo = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, appliance["device"]["id"]), config_entry_id
    )
    if remo is not None:
        device_info["via_device_id"] = remo.id
    return device_info


class NatureRemoApplianceEntity(CoordinatorEntity[NatureRemoCoordinator]):
    """The main entity of an appliance controlled through a Nature Remo."""

    _attr_has_entity_name = True
    # The entity represents the appliance itself, so it takes the device name.
    _attr_name = None

    def __init__(
        self, coordinator: NatureRemoCoordinator, appliance: dict[str, Any]
    ) -> None:
        """Initialize from the appliance as returned by the API."""
        super().__init__(coordinator)
        self._appliance_id: str = appliance["id"]
        self._attr_unique_id = appliance["id"]
        self._attr_device_info = appliance_device_info(
            coordinator.hass, coordinator.config_entry.entry_id, appliance
        )

    @property
    def appliance(self) -> dict[str, Any]:
        """Return the latest appliance data."""
        return self.coordinator.data["appliances"][self._appliance_id]

    @property
    def available(self) -> bool:
        """Unavailable when polling fails or the appliance left the account."""
        return (
            super().available
            and self._appliance_id in self.coordinator.data["appliances"]
        )


class NatureRemoDeviceEntity(CoordinatorEntity[NatureRemoCoordinator]):
    """An entity for a Nature Remo hardware device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NatureRemoCoordinator, device: dict[str, Any]
    ) -> None:
        """Initialize from the device as returned by the API."""
        super().__init__(coordinator)
        self._device_id: str = device["id"]
        self._attr_device_info = remo_device_info(device)

    @property
    def device(self) -> dict[str, Any]:
        """Return the latest device data."""
        return self.coordinator.data["devices"][self._device_id]

    @property
    def available(self) -> bool:
        """Unavailable when polling fails or the device left the account."""
        return super().available and self._device_id in self.coordinator.data["devices"]
