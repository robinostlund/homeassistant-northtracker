"""Config flow for North-Tracker."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NorthTracker, AuthenticationError, APIError, RateLimitError
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, LOGGER


class NorthTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for North-Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            if scan_interval < 5:
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_low"
            elif scan_interval > 1440:  # 24 hours
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_high"
            
            if not errors:
                session = async_get_clientsession(self.hass)
                api = NorthTracker(session)
                try:
                    await api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                    LOGGER.info("Authentication successful for %s", user_input[CONF_USERNAME])
                    
                    # Check if already configured
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME],
                        data=user_input
                    )
                except AuthenticationError:
                    LOGGER.warning("Authentication failed for %s: Invalid credentials", user_input[CONF_USERNAME])
                    errors["base"] = "invalid_auth"
                except RateLimitError:
                    LOGGER.warning("Rate limit exceeded during authentication")
                    errors["base"] = "rate_limit"
                except APIError as err:
                    LOGGER.error("API error during authentication: %s", err)
                    errors["base"] = "cannot_connect"
                except Exception:
                    LOGGER.exception("Unexpected error connecting to North-Tracker API")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=1440)
                ),
            }),
            errors=errors,
        )