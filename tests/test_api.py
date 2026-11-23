"""Tests for the Nature Remo API client."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import aiohttp
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.nature_remo.api import (
    NatureRemoAPI,
    NatureRemoApiError,
    NatureRemoAuthError,
    NatureRemoConnectionError,
    NatureRemoRateLimitError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import AC_ID, AC_SETTINGS_URL, APPLIANCES_URL, DEVICES_URL, TOKEN, USER_URL


@pytest.fixture
def client(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> NatureRemoAPI:
    """Return an API client bound to the mocked HTTP session."""
    return NatureRemoAPI(TOKEN, async_get_clientsession(hass))


async def test_reads_return_decoded_bodies(
    client: NatureRemoAPI, api: dict[str, Any], aioclient_mock: AiohttpClientMocker
) -> None:
    """Successful reads return the API payloads and send the token."""
    assert await client.get_user() == api["user"]
    assert await client.get_devices() == api["devices"]
    assert await client.get_appliances() == api["appliances"]

    assert [str(call[1]) for call in aioclient_mock.mock_calls] == [
        USER_URL,
        DEVICES_URL,
        APPLIANCES_URL,
    ]
    for call in aioclient_mock.mock_calls:
        assert call[3] == {"Authorization": f"Bearer {TOKEN}"}


async def test_set_aircon_settings(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker
) -> None:
    """Settings are posted as form fields and the new settings are returned."""
    settings = {"temp": "26", "mode": "cool", "vol": "auto", "dir": "", "button": ""}
    aioclient_mock.post(AC_SETTINGS_URL, json=settings)

    assert await client.set_aircon_settings(AC_ID, {"temperature": "26"}) == settings

    method, url, data, _ = aioclient_mock.mock_calls[0]
    assert (method, str(url), data) == ("POST", AC_SETTINGS_URL, {"temperature": "26"})


async def test_unauthorized(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected token raises an auth error carrying the API message."""
    aioclient_mock.get(
        DEVICES_URL,
        status=HTTPStatus.UNAUTHORIZED,
        json={"code": 401001, "message": "Unauthorized"},
    )

    with pytest.raises(NatureRemoAuthError) as err:
        await client.get_devices()

    assert err.value.status == 401
    assert err.value.message == "Unauthorized"


async def test_rate_limited_reports_reset_time(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 429 raises a rate limit error with the reset time from the headers."""
    aioclient_mock.get(
        APPLIANCES_URL,
        status=HTTPStatus.TOO_MANY_REQUESTS,
        json={"code": 429001, "message": "Too Many Requests"},
        headers={
            "X-Rate-Limit-Limit": "30",
            "X-Rate-Limit-Remaining": "0",
            "X-Rate-Limit-Reset": "1795420800",
        },
    )

    with pytest.raises(NatureRemoRateLimitError) as err:
        await client.get_appliances()

    assert err.value.reset == datetime.fromtimestamp(1795420800, UTC)


async def test_rate_limited_without_reset_header(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 429 without a usable reset header still raises, with no reset time."""
    aioclient_mock.get(
        APPLIANCES_URL,
        status=HTTPStatus.TOO_MANY_REQUESTS,
        text="slow down",
        headers={"X-Rate-Limit-Reset": "soon"},
    )

    with pytest.raises(NatureRemoRateLimitError) as err:
        await client.get_appliances()

    assert err.value.reset is None
    assert err.value.message == "Rate limit exceeded"


async def test_error_response_is_not_returned_as_data(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed write raises instead of handing back the error body."""
    aioclient_mock.post(
        AC_SETTINGS_URL,
        status=HTTPStatus.BAD_REQUEST,
        json={"code": 400001, "message": "Bad Request"},
    )

    with pytest.raises(NatureRemoApiError) as err:
        await client.set_aircon_settings(AC_ID, {"temperature": "99"})

    assert err.value.status == 400
    assert "Bad Request" in str(err.value)


async def test_server_error_with_non_json_body(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker
) -> None:
    """A gateway error page is reported as an API error."""
    aioclient_mock.get(
        DEVICES_URL, status=HTTPStatus.BAD_GATEWAY, text="<html>Bad Gateway</html>"
    )

    with pytest.raises(NatureRemoApiError) as err:
        await client.get_devices()

    assert err.value.status == 502
    assert err.value.message == "Request failed"


@pytest.mark.parametrize("body", ['{"message": "not a list"}', "not json"])
async def test_unusable_success_body(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker, body: str
) -> None:
    """A 200 with the wrong shape or invalid JSON is an API error."""
    aioclient_mock.get(DEVICES_URL, text=body)

    with pytest.raises(NatureRemoApiError):
        await client.get_devices()


@pytest.mark.parametrize("exc", [aiohttp.ClientConnectionError("boom"), TimeoutError()])
async def test_connection_problems(
    client: NatureRemoAPI, aioclient_mock: AiohttpClientMocker, exc: Exception
) -> None:
    """Network failures and timeouts raise a connection error."""
    aioclient_mock.get(DEVICES_URL, exc=exc)

    with pytest.raises(NatureRemoConnectionError):
        await client.get_devices()
