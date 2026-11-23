"""Check that Home Assistant can find and load the integration."""

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .conftest import REPO_ROOT

DOMAIN = "nature_remo"


async def test_integration_is_discovered(hass: HomeAssistant) -> None:
    """The loader finds the custom integration and reads its manifest."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert not integration.is_built_in
    assert integration.version is not None
    assert Path(integration.file_path).name == DOMAIN


async def test_integration_imports(hass: HomeAssistant) -> None:
    """The integration module and its platforms import on this Home Assistant."""
    integration = await async_get_integration(hass, DOMAIN)

    await integration.async_get_component()
    await integration.async_get_platforms(["climate", "sensor"])


def test_hacs_json_is_valid() -> None:
    """The Marketplace metadata file parses and names the integration."""
    hacs = json.loads((REPO_ROOT / "hacs.json").read_text())

    assert hacs["name"] == "Nature Remo"
