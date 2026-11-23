"""Tests for the Nature Remo sensors."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant

from . import (
    HUMIDITY_ENTITY,
    ILLUMINANCE_ENTITY,
    TEMPERATURE_ENTITY,
    load_json,
    mock_api,
)
from .conftest import SetupIntegration

POWER_ENTITY = "sensor.nature_remo_smart_meter"


@pytest.mark.parametrize(
    ("entity_id", "value", "unit", "device_class"),
    [
        (TEMPERATURE_ENTITY, "22.5", "°C", "temperature"),
        (HUMIDITY_ENTITY, "45", "%", "humidity"),
        (ILLUMINANCE_ENTITY, "120", "lx", "illuminance"),
    ],
)
async def test_device_sensors(
    hass: HomeAssistant,
    api: dict[str, Any],
    setup_integration: SetupIntegration,
    entity_id: str,
    value: str,
    unit: str,
    device_class: str,
) -> None:
    """Each Remo sensor reports a measurement usable for long-term statistics."""
    await setup_integration()

    state = hass.states.get(entity_id)
    assert state.state == value
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes["device_class"] == device_class
    assert state.attributes["state_class"] == "measurement"


async def test_only_reported_events_get_sensors(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A Remo that reports only temperature gets only a temperature sensor."""
    api["devices"][0]["newest_events"] = {
        "te": {"val": 21, "created_at": "2026-11-23T08:00:00Z"}
    }
    mock_api(aioclient_mock, api)
    await setup_integration()

    assert hass.states.get(TEMPERATURE_ENTITY).state == "21"
    assert hass.states.get(HUMIDITY_ENTITY) is None
    assert hass.states.get(ILLUMINANCE_ENTITY) is None


async def test_sensor_follows_updates(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Values follow the polled data; a vanished event becomes unknown."""
    await setup_integration()

    api["devices"][0]["newest_events"]["te"]["val"] = 23.1
    del api["devices"][0]["newest_events"]["hu"]
    mock_api(aioclient_mock, api)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(TEMPERATURE_ENTITY).state == "23.1"
    assert hass.states.get(HUMIDITY_ENTITY).state == "unknown"


async def test_smart_meter_power(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A smart meter reports its instantaneous power in watts."""
    api["appliances"].append(load_json("smart_meter.json"))
    mock_api(aioclient_mock, api)
    await setup_integration()

    state = hass.states.get(POWER_ENTITY)
    assert state.state == "540"
    assert state.name == "Nature Remo Smart Meter"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"
    assert state.attributes["state_class"] == "measurement"


async def test_smart_meter_without_power_property(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A meter that does not report instantaneous power has an unknown state."""
    meter = load_json("smart_meter.json")
    meter["smart_meter"]["echonetlite_properties"] = [
        prop
        for prop in meter["smart_meter"]["echonetlite_properties"]
        if prop["epc"] != 231
    ]
    api["appliances"].append(meter)
    mock_api(aioclient_mock, api)
    await setup_integration()

    assert hass.states.get(POWER_ENTITY).state == "unknown"
