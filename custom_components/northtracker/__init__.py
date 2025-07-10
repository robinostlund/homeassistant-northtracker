"""The North-Tracker integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up North-Tracker from a config entry."""
    coordinator = NorthTrackerDataUpdateCoordinator(hass, entry)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        LOGGER.error("Failed to setup North-Tracker integration: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up coordinator and logout if needed
        coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        try:
            if coordinator.api._token:
                await coordinator.api.logout()
                LOGGER.debug("Logged out from North-Tracker API")
        except Exception as err:
            LOGGER.warning("Error during logout: %s", err)
        
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok