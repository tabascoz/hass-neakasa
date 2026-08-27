"""Config flow for Neakasa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeakasaAPI
from .api_client import NeakasaApiClient
from .const import _LOGGER, DOMAIN
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
)
from .options_flow import NeakasaOptionsFlow


class NeakasaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Neakasa."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> NeakasaOptionsFlow:
        """Return the options flow."""
        return NeakasaOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step — credentials only."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            # One config entry per account
            account_uid = f"account:{username.lower()}"
            await self.async_set_unique_id(account_uid, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                session = async_get_clientsession(self.hass)
                api = NeakasaAPI(session, self.hass.async_add_executor_job)
                await api.connect(username, password)
                client = NeakasaApiClient(api)

                # Verify at least one CatLitter device exists
                devices = await client.get_devices()
                cat_devices = [
                    d for d in devices if d.get("categoryKey") == "CatLitter"
                ]
                if not cat_devices:
                    return self.async_abort(reason="no_devices_found")

                _LOGGER.debug(
                    "Account %s validated — %d CatLitter device(s) found",
                    username,
                    len(cat_devices),
                )

                return self.async_create_entry(
                    title=f"Neakasa ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

            except NeakasaApiClientAuthenticationError:
                errors["base"] = "authentication"
            except NeakasaApiClientCommunicationError:
                errors["base"] = "connection"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                },
            ),
            errors=errors,
        )
