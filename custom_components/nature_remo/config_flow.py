"""Config flow for the Nature Remo integration."""

from collections.abc import Mapping
import logging
from typing import Any

import probatio

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NatureRemoAPI, NatureRemoAuthError, NatureRemoError
from .const import (
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    DOMAIN,
)
from .coordinator import NatureRemoConfigEntry

_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE = "Nature Remo"
TOKEN_SCHEMA = probatio.Schema({probatio.Required(CONF_ACCESS_TOKEN): str})
OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_COOL_TEMP, default=DEFAULT_COOL_TEMP): probatio.Coerce(
            int
        ),
        probatio.Required(CONF_HEAT_TEMP, default=DEFAULT_HEAT_TEMP): probatio.Coerce(
            int
        ),
    }
)
PLACEHOLDERS = {"token_url": "https://home.nature.global/"}


class NatureRemoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nature Remo."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: NatureRemoConfigEntry,
    ) -> NatureRemoOptionsFlow:
        """Return the options flow."""
        return NatureRemoOptionsFlow()

    async def _async_get_user(
        self, token: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Look up the account for a token, returning it or an error key."""
        api = NatureRemoAPI(token, async_get_clientsession(self.hass))
        try:
            return await api.get_user(), None
        except NatureRemoAuthError:
            return None, "invalid_auth"
        except NatureRemoError as err:
            _LOGGER.debug("Could not validate the access token: %s", err)
            return None, "cannot_connect"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the access token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN]
            self._async_abort_entries_match({CONF_ACCESS_TOKEN: token})
            user, error = await self._async_get_user(token)
            if user is not None:
                await self.async_set_unique_id(user["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.get("nickname") or DEFAULT_TITLE,
                    data={CONF_ACCESS_TOKEN: token},
                )
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="user",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the configuration from configuration.yaml."""
        token = import_data[CONF_ACCESS_TOKEN]
        self._async_abort_entries_match({CONF_ACCESS_TOKEN: token})

        title = DEFAULT_TITLE
        user, error = await self._async_get_user(token)
        if error == "invalid_auth":
            return self.async_abort(reason="invalid_auth")
        if user is not None:
            await self.async_set_unique_id(user["id"])
            self._abort_if_unique_id_configured()
            title = user.get("nickname") or DEFAULT_TITLE
        # When the API cannot be reached the entry is still created (without a
        # unique id), so that setup keeps retrying instead of waiting for a restart.
        return self.async_create_entry(
            title=title,
            data={CONF_ACCESS_TOKEN: token},
            options={
                CONF_COOL_TEMP: import_data.get(CONF_COOL_TEMP, DEFAULT_COOL_TEMP),
                CONF_HEAT_TEMP: import_data.get(CONF_HEAT_TEMP, DEFAULT_HEAT_TEMP),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected access token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new access token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN]
            user, error = await self._async_get_user(token)
            if user is not None:
                entry = self._get_reauth_entry()
                await self.async_set_unique_id(user["id"])
                if entry.unique_id is not None:
                    self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=user["id"],
                    data_updates={CONF_ACCESS_TOKEN: token},
                )
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )


class NatureRemoOptionsFlow(OptionsFlowWithReload):
    """Handle Nature Remo options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the default target temperatures."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
