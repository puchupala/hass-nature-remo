"""Tests for the Nature Remo integration."""

from copy import deepcopy
from http import HTTPStatus
import json
from pathlib import Path
from typing import Any

from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

FIXTURES = Path(__file__).parent / "fixtures"

API_URL = "https://api.nature.global/1"
USER_URL = f"{API_URL}/users/me"
DEVICES_URL = f"{API_URL}/devices"
APPLIANCES_URL = f"{API_URL}/appliances"
AC_ID = "appliance-ac"
AC_SETTINGS_URL = f"{APPLIANCES_URL}/{AC_ID}/aircon_settings"
DEVICE_ID = "device-mio"

TOKEN = "test-token"

AC_ENTITY = "climate.nature_remo_air_conditioner"
TEMPERATURE_ENTITY = "sensor.nature_remo_mio_temperature"
HUMIDITY_ENTITY = "sensor.nature_remo_mio_humidity"
ILLUMINANCE_ENTITY = "sensor.nature_remo_mio_illuminance"


def load_json(name: str) -> Any:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


def api_data() -> dict[str, Any]:
    """Return a fresh copy of the default API responses."""
    return {
        "user": load_json("user.json"),
        "devices": load_json("devices.json"),
        "appliances": load_json("appliances.json"),
    }


def mock_api(
    aioclient_mock: AiohttpClientMocker, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Make the mocked API answer successfully, replacing earlier mocks."""
    data = deepcopy(data) if data is not None else api_data()
    aioclient_mock.clear_requests()
    aioclient_mock.get(USER_URL, json=data["user"])
    aioclient_mock.get(DEVICES_URL, json=data["devices"])
    aioclient_mock.get(APPLIANCES_URL, json=data["appliances"])
    return data


def mock_api_error(
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Make every mocked API read fail with the given status."""
    aioclient_mock.clear_requests()
    for url in (USER_URL, DEVICES_URL, APPLIANCES_URL):
        aioclient_mock.get(url, status=status, json=body or {}, headers=headers)
