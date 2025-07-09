"""Config flow for North-Tracker."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NorthTracker, AuthenticationError
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL

class NorthTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for North-Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = NorthTracker(session)
            try:
                await api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
            }),
            errors=errors,
        )