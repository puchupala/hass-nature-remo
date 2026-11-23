"""Tests for the Nature Remo climate entity."""

from http import HTTPStatus
from typing import Any

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import AC_ENTITY, AC_SETTINGS_URL
from .conftest import SetupIntegration


async def test_set_temperature(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """Setting a temperature posts it and applies the returned settings."""
    await setup_integration()
    settings = {**api["appliances"][0]["settings"], "temp": "26"}
    aioclient_mock.post(AC_SETTINGS_URL, json=settings)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": AC_ENTITY, "temperature": 26},
        blocking=True,
    )

    assert aioclient_mock.mock_calls[-1][2] == {"temperature": "26"}
    assert hass.states.get(AC_ENTITY).attributes["temperature"] == 26


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
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": AC_ENTITY, "temperature": 26},
            blocking=True,
        )

    state = hass.states.get(AC_ENTITY)
    assert state.state == "cool"
    assert state.attributes["temperature"] == 25
