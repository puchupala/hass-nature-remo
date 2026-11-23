"""Tests for the Nature Remo config, reauth and options flows."""

from http import HTTPStatus
from typing import Any

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import TOKEN, USER_ID, mock_api, mock_api_error
from .conftest import DOMAIN, SetupIntegration

UNAUTHORIZED = {"code": 401001, "message": "Unauthorized"}


async def test_user_flow_creates_entry(hass: HomeAssistant, api: dict[str, Any]) -> None:
    """Entering a valid token creates an entry named after the account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": TOKEN}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test User"
    assert result["data"] == {"access_token": TOKEN}
    assert result["result"].unique_id == USER_ID


async def test_user_flow_recovers_from_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected token and an unreachable API show errors and allow a retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_api_error(aioclient_mock, HTTPStatus.UNAUTHORIZED, UNAUTHORIZED)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api_error(aioclient_mock, HTTPStatus.BAD_GATEWAY)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": TOKEN}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": TOKEN}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_account_already_configured(
    hass: HomeAssistant, api: dict[str, Any], config_entry: MockConfigEntry
) -> None:
    """The same account cannot be added twice, even with another token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": "another-token-of-the-same-account"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_yaml_is_imported(hass: HomeAssistant, api: dict[str, Any]) -> None:
    """A YAML block becomes a working config entry and raises a notice."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"access_token": TOKEN, "cool_temperature": 26}},
    )
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.source == SOURCE_IMPORT
    assert entry.unique_id == USER_ID
    assert entry.title == "Test User"
    assert entry.data == {"access_token": TOKEN}
    assert entry.options == {"cool_temperature": 26, "heat_temperature": 20}
    assert hass.states.get("climate.nature_remo_air_conditioner") is not None
    assert ir.async_get(hass).async_get_issue(DOMAIN, "deprecated_yaml") is not None


async def test_yaml_is_imported_only_once(
    hass: HomeAssistant, api: dict[str, Any], config_entry: MockConfigEntry
) -> None:
    """YAML that is still present on a later start does not add a second entry."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"access_token": TOKEN}})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]
    assert ir.async_get(hass).async_get_issue(DOMAIN, "deprecated_yaml") is not None


async def test_yaml_import_while_api_is_unreachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With the API down the entry is still created and its setup is retried."""
    mock_api_error(aioclient_mock, HTTPStatus.BAD_GATEWAY)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"access_token": TOKEN}})
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.unique_id is None
    assert entry.state.name == "SETUP_RETRY"


async def test_yaml_import_with_rejected_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected YAML token creates no entry and explains why."""
    mock_api_error(aioclient_mock, HTTPStatus.UNAUTHORIZED, UNAUTHORIZED)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"access_token": TOKEN}})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "yaml_import_invalid_auth") is not None
    assert issues.async_get_issue(DOMAIN, "deprecated_yaml") is None


async def test_reauth_updates_token(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """Reauthentication stores the new token for the same account."""
    entry = await setup_integration()

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"access_token": "new-token"}
    assert aioclient_mock.mock_calls[-1][3] == {"Authorization": "Bearer new-token"}


async def test_reauth_rejects_other_account(
    hass: HomeAssistant,
    api: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    setup_integration: SetupIntegration,
) -> None:
    """A token of a different account is not accepted for reauthentication."""
    entry = await setup_integration()
    mock_api(aioclient_mock, {**api, "user": {"id": "someone-else", "nickname": "X"}})

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"access_token": "new-token"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == {"access_token": TOKEN}


async def test_options_flow(
    hass: HomeAssistant, api: dict[str, Any], setup_integration: SetupIntegration
) -> None:
    """The default temperatures can be changed from the options."""
    entry = await setup_integration()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"cool_temperature": 26, "heat_temperature": 22}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"cool_temperature": 26, "heat_temperature": 22}
