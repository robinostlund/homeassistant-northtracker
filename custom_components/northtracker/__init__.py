"""The North-Tracker integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up North-Tracker from a config entry."""
    LOGGER.debug("Setting up North-Tracker integration for entry: %s", entry.title)
    LOGGER.debug("Config entry data keys: %s", list(entry.data.keys()))
    
    coordinator = NorthTrackerDataUpdateCoordinator(hass, entry)
    
    try:
        LOGGER.debug("Performing initial coordinator refresh")
        await coordinator.async_config_entry_first_refresh()
        LOGGER.info("North-Tracker coordinator initial refresh completed successfully")
    except Exception as err:
        LOGGER.error("Failed to setup North-Tracker integration: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    LOGGER.debug("Coordinator stored in hass.data for entry %s", entry.entry_id)

    LOGGER.debug("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.info("North-Tracker integration setup completed for %s", entry.title)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading North-Tracker integration for entry: %s", entry.title)
    
    # Unload platforms
    LOGGER.debug("Unloading platforms: %s", PLATFORMS)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up coordinator and logout if needed
        coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        try:
            if coordinator.api._token:
                LOGGER.debug("Logging out from North-Tracker API")
                await coordinator.api.logout()
                LOGGER.debug("Logged out from North-Tracker API")
            else:
                LOGGER.debug("No active token, skipping logout")
        except Exception as err:
            LOGGER.warning("Error during logout: %s", err)
        
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.debug("Coordinator removed from hass.data")
        LOGGER.info("North-Tracker integration unloaded successfully for %s", entry.title)
    else:
        LOGGER.error("Failed to unload platforms for North-Tracker integration")

    return unload_ok