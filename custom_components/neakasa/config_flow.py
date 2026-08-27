"""Config flow for Neakasa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeakasaAPI
from .api_client import NeakasaApiClient
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
)
from .const import DOMAIN, _LOGGER
from .options_flow import NeakasaOptionsFlow


class NeakasaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Neakasa."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> NeakasaOptionsFlow:
        """Return the options flow."""
        return NeakasaOptionsFlow(config_entry)

    async def async_migrate_entry(self, hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
        """Migrate config entry from VERSION 1 → 2."""
        if config_entry.version == 1:
            _LOGGER.debug("Migrating config entry %s from V1 to V2", config_entry.entry_id)

            new_data = {
                CONF_USERNAME: config_entry.data[CONF_USERNAME],
                CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
            }
            new_unique_id = f"account:{new_data[CONF_USERNAME].lower()}"

            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                unique_id=new_unique_id,
                version=2,
            )
            _LOGGER.debug("Migrated config entry %s to V2", config_entry.entry_id)

        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None,
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
                cat_devices = [d for d in devices if d.get("categoryKey") == "CatLitter"]
                if not cat_devices:
                    return self.async_abort(reason="no_devices_found")

                _LOGGER.debug(
                    "Account %s validated — %d CatLitter device(s) found",
                    username, len(cat_devices),
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

