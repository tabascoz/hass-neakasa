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


async def _validate_credentials(
    hass: Any, username: str, password: str
) -> tuple[NeakasaApiClient | None, str | None]:
    """
    Try authenticating with *username* and *password*.

    Returns ``(client, None)`` on success or ``(None, error_key)`` on failure.
    """
    try:
        session = async_get_clientsession(hass)
        api = NeakasaAPI(session, hass.async_add_executor_job)
        await api.connect(username, password)
        client = NeakasaApiClient(api)
        devices = await client.get_devices()
        cat_devices = [d for d in devices if d.get("categoryKey") == "CatLitter"]
        if not cat_devices:
            return None, "no_devices_found"
        return client, None  # noqa: TRY300
    except NeakasaApiClientAuthenticationError:
        return None, "authentication"
    except NeakasaApiClientCommunicationError:
        return None, "connection"


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

            account_uid = f"account:{username.lower()}"
            await self.async_set_unique_id(account_uid, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            _client, error = await _validate_credentials(self.hass, username, password)
            if error is not None:
                errors["base"] = error
            else:
                _LOGGER.debug(
                    "Account %s validated — credentials accepted",
                    username,
                )
                return self.async_create_entry(
                    title=f"Neakasa ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

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

    # ------------------------------------------------------------------
    # Reconfigure flow
    # ------------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle entry reconfigure — update username/password."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            _client, error = await _validate_credentials(self.hass, username, password)
            if error is not None:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    title=f"Neakasa ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=f"account:{username.lower()}",
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                },
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Reauth flow
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle reauth triggered by persistent auth failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with new credentials."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            _client, error = await _validate_credentials(self.hass, username, password)
            if error is not None:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    title=f"Neakasa ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=f"account:{username.lower()}",
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                },
            ),
            description_placeholders={
                "username": entry.data.get(CONF_USERNAME, ""),
            },
            errors=errors,
        )
