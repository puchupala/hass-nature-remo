"""Shared fixtures for the Nature Remo tests."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant

from . import TOKEN, USER_ID, mock_api

REPO_ROOT = Path(__file__).parent.parent
DOMAIN = "nature_remo"

type SetupIntegration = Callable[[], Awaitable[MockConfigEntry]]


@pytest.fixture
def hass_config_dir(tmp_path: Path) -> str:
    """Use a temporary config directory that exposes this repo's integration."""
    (tmp_path / "custom_components").symlink_to(
        REPO_ROOT / "custom_components", target_is_directory=True
    )
    return str(tmp_path)


@pytest.fixture
def api(aioclient_mock: AiohttpClientMocker) -> dict[str, Any]:
    """Mock a healthy Nature Remo API and return the data it serves."""
    return mock_api(aioclient_mock)


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry that has been added to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test User",
        unique_id=USER_ID,
        data={"access_token": TOKEN},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> SetupIntegration:
    """Return a function that sets up the config entry."""

    async def _setup() -> MockConfigEntry:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return _setup
