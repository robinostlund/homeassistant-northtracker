"""The North-Tracker integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up North-Tracker from a config entry."""
    # Check for empty/corrupted config entries
    if not entry.data:
        LOGGER.error("Config entry %s has no data - likely corrupted", entry.entry_id)
        return False
    
    coordinator = NorthTrackerDataUpdateCoordinator(hass, entry)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        LOGGER.error("Failed to setup North-Tracker integration: %s", err)
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.info("North-Tracker integration setup completed for %s", entry.title)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up coordinator and logout if needed
        coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        try:
            if coordinator.api.is_authenticated:
                await coordinator.api.logout()
        except Exception as err:
            LOGGER.warning("Error during logout: %s", err)
        
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.info("North-Tracker integration unloaded for %s", entry.title)
    else:
        LOGGER.error("Failed to unload platforms for North-Tracker integration")

    return unload_ok