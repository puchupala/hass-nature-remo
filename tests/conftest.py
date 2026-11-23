"""Shared fixtures for the Nature Remo tests."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TOKEN, mock_api

REPO_ROOT = Path(__file__).parent.parent
DOMAIN = "nature_remo"

type SetupIntegration = Callable[..., Awaitable[None]]


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
async def setup_integration(hass: HomeAssistant) -> AsyncGenerator[SetupIntegration]:
    """Return a function that sets up the integration."""

    async def _setup(**config: Any) -> None:
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"access_token": TOKEN, **config}}
        )
        await hass.async_block_till_done()

    yield _setup

    # YAML setup has no unload step, so stop the polling timer explicitly.
    if DOMAIN in hass.data:
        await hass.data[DOMAIN]["coordinator"].async_shutdown()
