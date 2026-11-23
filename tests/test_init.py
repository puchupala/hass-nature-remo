"""Tests for setting up the integration and polling the API."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import AC_ENTITY, TEMPERATURE_ENTITY, mock_api, mock_api_error
from .conftest import SetupIntegration

POLL = timedelta(seconds=60)


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move time forward and let scheduled work run."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_creates_entities(
    hass: HomeAssistant, api: dict[str, Any], setup_integration: SetupIntegration
) -> None:
    """Setup fetches both lists and creates the climate and sensor entities."""
    await setup_integration()

    assert hass.states.get(AC_ENTITY).state == "cool"
    assert hass.states.get(TEMPERATURE_ENTITY).state == "22.5"


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
