"""Tests for setting up the integration and polling the API."""

from copy import deepcopy
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    AC_ENTITY,
    AC_ID,
    DEVICE_ID,
    HUMIDITY_ENTITY,
    ILLUMINANCE_ENTITY,
    TEMPERATURE_ENTITY,
    mock_api,
    mock_api_error,
)
from .conftest import DOMAIN, SetupIntegration

POLL = timedelta(seconds=60)
ALL_ENTITIES = (AC_ENTITY, TEMPERATURE_ENTITY, HUMIDITY_ENTITY, ILLUMINANCE_ENTITY)


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move time forward and let scheduled work run."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_setup_and_unload(
    hass: HomeAssistant, api: dict[str, Any], setup_integration: SetupIntegration
) -> None:
    """Setup creates the entities with their established names and IDs."""
    entry = await setup_integration()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(AC_ENTITY).state == "cool"
    assert hass.states.get(AC_ENTITY).name == "Nature Remo Air Conditioner"
    assert hass.states.get(TEMPERATURE_ENTITY).state == "22.5"
    assert hass.states.get(TEMPERATURE_ENTITY).name == "Nature Remo Mio Temperature"
    assert hass.states.get(HUMIDITY_ENTITY).name == "Nature Remo Mio Humidity"
    assert hass.states.get(ILLUMINANCE_ENTITY).name == "Nature Remo Mio Illuminance"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(AC_ENTITY).state == "unavailable"


async def test_devices_are_registered(
    hass: HomeAssistant, api: dict[str, Any], setup_integration: SetupIntegration
) -> None:
    """The Remo and the appliance behind it are registered as linked devices."""
    entry = await setup_integration()
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    remo = devices.async_get_device_by_identifier((DOMAIN, DEVICE_ID), entry.entry_id)
    assert remo.name == "Nature Remo Mio"
    assert remo.manufacturer == "Nature"
    assert remo.model == "Remo"
    assert remo.sw_version == "1.14.6"
    assert remo.serial_number == "1W320010000001"

    appliance = devices.async_get_device_by_identifier((DOMAIN, AC_ID), entry.entry_id)
    assert appliance.name == "Nature Remo Air Conditioner"
    assert appliance.via_device_id == remo.id

    assert entities.async_get(TEMPERATURE_ENTITY).device_id == remo.id
    assert entities.async_get(AC_ENTITY).device_id == appliance.id


async def test_existing_entity_ids_are_kept(
    hass: HomeAssistant, api: dict[str, Any], setup_integration: SetupIntegration
) -> None:
    """Entities registered by the YAML-era integration keep their entity IDs."""
    registry = er.async_get(hass)
    # As left behind by the old integration: no config entry, no device.
    registry.async_get_or_create(
        "climate",
        DOMAIN,
        AC_ID,
        suggested_object_id="bedroom_ac",
        has_entity_name=False,
        original_name="Nature Remo Air Conditioner ",
    )
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DEVICE_ID}-te",
        suggested_object_id="bedroom_temperature",
        has_entity_name=False,
        original_name="Nature Remo Mio Temperature",
    )

    entry = await setup_integration()

    assert hass.states.get("climate.bedroom_ac").state == "cool"
    assert hass.states.get("climate.bedroom_ac").name == "Nature Remo Air Conditioner"
    assert hass.states.get("sensor.bedroom_temperature").state == "22.5"
    assert (
        hass.states.get("sensor.bedroom_temperature").name
        == "Nature Remo Mio Temperature"
    )
    assert hass.states.get(AC_ENTITY) is None
    assert hass.states.get(TEMPERATURE_ENTITY) is None
    for entity_id in ("climate.bedroom_ac", "sensor.bedroom_temperature"):
        registered = registry.async_get(entity_id)
        assert registered.config_entry_id == entry.entry_id
        assert registered.device_id is not None


async def test_first_refresh_failure_is_retried(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """If the API is down at startup, setup is retried until it answers."""
    mock_api_error(aioclient_mock, HTTPStatus.BAD_GATEWAY)
    entry = await setup_integration()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get(AC_ENTITY) is None

    mock_api(aioclient_mock)
    await _advance(hass, freezer, timedelta(minutes=1))

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(AC_ENTITY).state == "cool"


async def test_rejected_token_starts_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A rejected token fails setup and asks the user for a new one."""
    mock_api_error(
        aioclient_mock,
        HTTPStatus.UNAUTHORIZED,
        {"code": 401001, "message": "Unauthorized"},
    )
    entry = await setup_integration()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_polls_once_per_interval(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each polling cycle costs exactly two API requests."""
    await setup_integration()
    assert aioclient_mock.call_count == 2

    await _advance(hass, freezer, POLL)
    assert aioclient_mock.call_count == 4

    await _advance(hass, freezer, POLL)
    assert aioclient_mock.call_count == 6


async def test_rate_limit_backs_off_until_reset(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After a 429 the next poll waits for the reported reset time."""
    await setup_integration()

    reset = dt_util.utcnow() + POLL + timedelta(minutes=4)
    mock_api_error(
        aioclient_mock,
        HTTPStatus.TOO_MANY_REQUESTS,
        {"code": 429001, "message": "Too Many Requests"},
        {"X-Rate-Limit-Reset": str(int(reset.timestamp()))},
    )
    await _advance(hass, freezer, POLL)
    # The first request of the cycle was rejected; the second was not sent.
    assert aioclient_mock.call_count == 1

    # The normal interval passes several times without another request.
    await _advance(hass, freezer, POLL)
    await _advance(hass, freezer, POLL)
    assert aioclient_mock.call_count == 1

    # Polling resumes once the window has reset.
    mock_api(aioclient_mock)
    await _advance(hass, freezer, timedelta(minutes=2, seconds=5))
    assert aioclient_mock.call_count == 2


async def test_entities_unavailable_while_polling_fails(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stale values are not shown as current; they return when polling works."""
    await setup_integration()

    mock_api_error(aioclient_mock, HTTPStatus.BAD_GATEWAY)
    await _advance(hass, freezer, POLL)
    for entity_id in ALL_ENTITIES:
        assert hass.states.get(entity_id).state == "unavailable"

    mock_api(aioclient_mock)
    await _advance(hass, freezer, POLL)
    assert hass.states.get(AC_ENTITY).state == "cool"
    assert hass.states.get(TEMPERATURE_ENTITY).state == "22.5"


async def test_removed_appliance_and_device_become_unavailable(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities whose appliance or device left the account turn unavailable."""
    await setup_integration()

    mock_api(aioclient_mock, {**api, "appliances": [], "devices": []})
    await _advance(hass, freezer, POLL)

    for entity_id in ALL_ENTITIES:
        assert hass.states.get(entity_id).state == "unavailable"


async def test_new_appliance_and_device_are_added_without_restart(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An appliance and a Remo added to the account later show up by themselves."""
    await setup_integration()
    assert hass.states.get("climate.nature_remo_living_room_ac") is None

    second_ac = deepcopy(api["appliances"][0])
    second_ac.update(id="appliance-ac-2", nickname="Living Room AC")
    second_remo = deepcopy(api["devices"][0])
    second_remo.update(id="device-2", name="Remo mini")
    second_remo["newest_events"] = {"te": {"val": 19, "created_at": "2026-11-23T08:00:00Z"}}
    mock_api(
        aioclient_mock,
        {
            **api,
            "appliances": [*api["appliances"], second_ac],
            "devices": [*api["devices"], second_remo],
        },
    )
    await _advance(hass, freezer, POLL)

    assert hass.states.get("climate.nature_remo_living_room_ac").state == "cool"
    assert hass.states.get("sensor.nature_remo_remo_mini_temperature").state == "19"
    assert hass.states.get("sensor.nature_remo_remo_mini_humidity") is None
