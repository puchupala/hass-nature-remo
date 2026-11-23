"""Tests for the Nature Remo climate entity."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import AC_ENTITY, AC_SETTINGS_URL, mock_api
from .conftest import SetupIntegration


def _mock_settings(
    aioclient_mock: AiohttpClientMocker, api: dict[str, Any], **changes: str
) -> None:
    """Make the API answer the next command with the given resulting settings."""
    aioclient_mock.post(
        AC_SETTINGS_URL, json={**api["appliances"][0]["settings"], **changes}
    )


async def _call(hass: HomeAssistant, service: str, **data: Any) -> None:
    await hass.services.async_call(
        "climate", service, {"entity_id": AC_ENTITY, **data}, blocking=True
    )


def _sent(aioclient_mock: AiohttpClientMocker) -> dict[str, str]:
    """Return the form fields of the last request."""
    return aioclient_mock.mock_calls[-1][2]


async def test_state(
    hass: HomeAssistant,
    api: dict[str, Any],
    setup_integration: SetupIntegration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The entity reflects the AC settings and the Remo's room temperature."""
    await setup_integration()

    state = hass.states.get(AC_ENTITY)
    assert state.state == "cool"
    assert state.attributes["temperature"] == 25
    assert state.attributes["current_temperature"] == 22.5
    assert state.attributes["fan_mode"] == "auto"
    assert state.attributes["fan_modes"] == ["1", "2", "3", "auto"]
    assert state.attributes["swing_mode"] == "swing"
    assert state.attributes["swing_modes"] == ["1", "2", "3", "swing"]
    assert state.attributes["min_temp"] == 18
    assert state.attributes["max_temp"] == 32
    assert state.attributes["target_temp_step"] == 0.5
    assert state.attributes["hvac_modes"] == [
        "auto",
        "fan_only",
        "cool",
        "dry",
        "heat",
        "off",
    ]
    assert state.attributes["supported_features"] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    assert state.attributes["previous_target_temperature"]["cool"] == "25"
    assert "deprecated" not in caplog.text


@pytest.mark.parametrize(("requested", "sent"), [(26, "26"), (25.5, "25.5")])
async def test_set_temperature(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    requested: float,
    sent: str,
) -> None:
    """Whole temperatures are sent without a decimal point."""
    await setup_integration()
    _mock_settings(aioclient_mock, api, temp=sent)

    await _call(hass, "set_temperature", temperature=requested)

    assert _sent(aioclient_mock) == {"temperature": sent}
    assert hass.states.get(AC_ENTITY).attributes["temperature"] == requested


async def test_mode_change_uses_default_then_remembered_temperature(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A mode gets its default temperature first and its last one afterwards."""
    await setup_integration()

    _mock_settings(aioclient_mock, api, mode="warm", temp="20")
    await _call(hass, "set_hvac_mode", hvac_mode="heat")
    assert _sent(aioclient_mock) == {"operation_mode": "warm", "temperature": "20"}
    state = hass.states.get(AC_ENTITY)
    assert state.state == "heat"
    assert (state.attributes["min_temp"], state.attributes["max_temp"]) == (14, 30)
    assert state.attributes["target_temp_step"] == 1

    aioclient_mock.clear_requests()
    _mock_settings(aioclient_mock, api, mode="cool", temp="25")
    await _call(hass, "set_hvac_mode", hvac_mode="cool")
    assert _sent(aioclient_mock) == {"operation_mode": "cool", "temperature": "25"}


async def test_default_temperatures_come_from_options(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    setup_integration: SetupIntegration,
) -> None:
    """The configured default temperature is used for a mode's first use."""
    hass.config_entries.async_update_entry(
        config_entry, options={"cool_temperature": 26, "heat_temperature": 22}
    )
    await setup_integration()
    _mock_settings(aioclient_mock, api, mode="warm", temp="22")

    await _call(hass, "set_hvac_mode", hvac_mode="heat")

    assert _sent(aioclient_mock) == {"operation_mode": "warm", "temperature": "22"}


async def test_turn_off_and_on(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """Turning on returns to the mode the AC was in before it was turned off."""
    await setup_integration()

    _mock_settings(aioclient_mock, api, button="power-off")
    await _call(hass, "turn_off")
    assert _sent(aioclient_mock) == {"button": "power-off"}
    assert hass.states.get(AC_ENTITY).state == "off"

    aioclient_mock.clear_requests()
    _mock_settings(aioclient_mock, api)
    await _call(hass, "turn_on")
    assert _sent(aioclient_mock) == {"operation_mode": "cool", "temperature": "25"}
    assert hass.states.get(AC_ENTITY).state == "cool"


async def test_set_fan_and_swing_mode(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """Fan and swing modes are sent as air volume and direction."""
    await setup_integration()

    _mock_settings(aioclient_mock, api, vol="2")
    await _call(hass, "set_fan_mode", fan_mode="2")
    assert _sent(aioclient_mock) == {"air_volume": "2"}
    assert hass.states.get(AC_ENTITY).attributes["fan_mode"] == "2"

    aioclient_mock.clear_requests()
    _mock_settings(aioclient_mock, api, vol="2", dir="1")
    await _call(hass, "set_swing_mode", swing_mode="1")
    assert _sent(aioclient_mock) == {"air_direction": "1"}
    assert hass.states.get(AC_ENTITY).attributes["swing_mode"] == "1"


async def test_mode_without_temperature_setting(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """Fan-only mode has no target temperature and no empty 0-0 range."""
    api["appliances"][0]["settings"].update(mode="blow", temp="")
    mock_api(aioclient_mock, api)
    await setup_integration()

    state = hass.states.get(AC_ENTITY)
    assert state.state == "fan_only"
    assert state.attributes.get("temperature") is None
    assert not (
        state.attributes["supported_features"] & ClimateEntityFeature.TARGET_TEMPERATURE
    )
    assert state.attributes["min_temp"] < state.attributes["max_temp"]


async def test_remo_without_temperature_sensor(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Without a room temperature the entity still works and keeps updating."""
    del api["devices"][0]["newest_events"]["te"]
    mock_api(aioclient_mock, api)
    await setup_integration()
    assert hass.states.get(AC_ENTITY).attributes["current_temperature"] is None

    api["appliances"][0]["settings"]["temp"] = "27"
    mock_api(aioclient_mock, api)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(AC_ENTITY)
    assert state.attributes["temperature"] == 27
    assert state.attributes["current_temperature"] is None


async def test_failed_command_raises_and_keeps_state(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A rejected command is reported to the caller and leaves the state alone."""
    await setup_integration()
    aioclient_mock.post(
        AC_SETTINGS_URL,
        status=HTTPStatus.BAD_REQUEST,
        json={"code": 400001, "message": "Bad Request"},
    )

    with pytest.raises(HomeAssistantError, match="Bad Request"):
        await _call(hass, "set_temperature", temperature=26)

    state = hass.states.get(AC_ENTITY)
    assert state.state == "cool"
    assert state.attributes["temperature"] == 25
