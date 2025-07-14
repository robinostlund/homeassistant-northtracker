"""Config flow for North-Tracker."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NorthTracker, AuthenticationError, APIError, RateLimitError
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, MIN_UPDATE_INTERVAL, MAX_UPDATE_INTERVAL, LOGGER


class NorthTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for North-Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        LOGGER.debug("Config flow step_user called with input: %s", bool(user_input))
        errors = {}
        if user_input is not None:
            LOGGER.debug("Processing user input for username: %s", user_input.get(CONF_USERNAME))
            
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            LOGGER.debug("Validating scan interval: %d minutes", scan_interval)
            
            if scan_interval < MIN_UPDATE_INTERVAL:
                LOGGER.warning("Scan interval too low: %d minutes", scan_interval)
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_low"
            elif scan_interval > MAX_UPDATE_INTERVAL:
                LOGGER.warning("Scan interval too high: %d minutes", scan_interval)
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_high"
            
            if not errors:
                LOGGER.debug("Scan interval validation passed, testing API connection")
                session = async_get_clientsession(self.hass)
                api = NorthTracker(session)
                try:
                    await api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                    LOGGER.info("Authentication successful for %s", user_input[CONF_USERNAME])
                    
                    # Check if already configured
                    LOGGER.debug("Checking for duplicate configuration")
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()
                    
                    LOGGER.debug("Creating config entry for %s", user_input[CONF_USERNAME])
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
            else:
                LOGGER.debug("Scan interval validation failed, showing form with errors")

        LOGGER.debug("Showing config form with errors: %s", errors)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                    vol.Coerce(float), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
                ),
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """Handle reauth flow."""
        LOGGER.debug("Starting reauth flow for entry: %s", entry_data.get(CONF_USERNAME))
        self.reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle reauth confirmation."""
        errors = {}
        
        if user_input is not None:
            LOGGER.debug("Processing reauth input for username: %s", user_input.get(CONF_USERNAME))
            
            session = async_get_clientsession(self.hass)
            api = NorthTracker(session)
            try:
                await api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                LOGGER.info("Reauth successful for %s", user_input[CONF_USERNAME])
                
                # Update the existing entry with new credentials
                new_data = self.reauth_entry.data.copy()
                new_data.update({
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                })
                
                # Update scan interval if provided
                if CONF_SCAN_INTERVAL in user_input:
                    new_data[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
                
                LOGGER.debug("Updating config entry with new credentials")
                LOGGER.debug("New data keys: %s", list(new_data.keys()))
                LOGGER.debug("New data: %s", {k: "***" if "password" in k.lower() else v for k, v in new_data.items()})
                
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=new_data, title=user_input[CONF_USERNAME]
                )
                
                LOGGER.debug("Config entry updated via reauth, reloading integration")
                # Reload the integration to use new credentials
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                
                return self.async_abort(reason="reauth_successful")
                
            except AuthenticationError:
                LOGGER.warning("Reauth failed for %s: Invalid credentials", user_input[CONF_USERNAME])
                errors["base"] = "invalid_auth"
            except RateLimitError:
                LOGGER.warning("Rate limit exceeded during reauth")
                errors["base"] = "rate_limit"
            except APIError as err:
                LOGGER.error("API error during reauth: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"

        # Show reauth form
        current_username = self.reauth_entry.data.get(CONF_USERNAME, "") if self.reauth_entry else ""
        current_scan_interval = self.reauth_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL) if self.reauth_entry else DEFAULT_UPDATE_INTERVAL
        
        LOGGER.debug("Showing reauth form for user: %s", current_username)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=current_username): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.All(
                    vol.Coerce(float), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
                ),
            }),
            errors=errors,
            description_placeholders={"username": current_username},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle reconfigure flow."""
        LOGGER.debug("Starting reconfigure flow")
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is not None:
            LOGGER.debug("Processing reconfigure input for username: %s", user_input.get(CONF_USERNAME))
            
            # If password is empty, keep the existing password
            if not user_input.get(CONF_PASSWORD):
                LOGGER.debug("Password field empty, keeping existing password")
                user_input[CONF_PASSWORD] = entry.data.get(CONF_PASSWORD)
            
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            if scan_interval < MIN_UPDATE_INTERVAL or scan_interval > MAX_UPDATE_INTERVAL:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._get_reconfigure_schema(entry),
                    errors={"scan_interval": "scan_interval_invalid"},
                )
            
            session = async_get_clientsession(self.hass)
            api = NorthTracker(session)
            try:
                await api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                LOGGER.info("Reconfigure authentication successful for %s", user_input[CONF_USERNAME])
                
                # Update the entry
                LOGGER.debug("Updating config entry with reconfigured settings")
                LOGGER.debug("User input keys: %s", list(user_input.keys()))
                LOGGER.debug("User input data: %s", {k: "***" if "password" in k.lower() else v for k, v in user_input.items()})
                
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=user_input,
                    title=user_input[CONF_USERNAME]
                )
                
                LOGGER.debug("Config entry updated, reloading integration")
                # Reload the integration
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                return self.async_abort(reason="reconfigure_successful")
                
            except AuthenticationError:
                LOGGER.warning("Reconfigure failed for %s: Invalid credentials", user_input[CONF_USERNAME])
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._get_reconfigure_schema(entry),
                    errors={"base": "invalid_auth"},
                )
            except (RateLimitError, APIError):
                LOGGER.error("API error during reconfigure")
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._get_reconfigure_schema(entry),
                    errors={"base": "cannot_connect"},
                )
            except Exception:
                LOGGER.exception("Unexpected error during reconfigure")
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._get_reconfigure_schema(entry),
                    errors={"base": "unknown"},
                )

        # Show reconfigure form with current values
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._get_reconfigure_schema(entry),
        )

    def _get_reconfigure_schema(self, entry: config_entries.ConfigEntry) -> vol.Schema:
        """Get the reconfigure schema with current values as defaults."""
        return vol.Schema({
            vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ): vol.All(vol.Coerce(float), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)),
        })