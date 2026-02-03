"""The North-Tracker integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue, async_delete_issue

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
    
    # Clean up stale devices and entities
    await async_cleanup_stale_devices(hass, entry, coordinator)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Clear any previous issues since setup was successful
    async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_api_error")
    async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_rate_limit")
    
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


async def async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: NorthTrackerDataUpdateCoordinator,
) -> None:
    """Remove devices and entities that no longer exist in the API."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    
    # Get current device IDs from the API
    current_device_ids = {str(device_id) for device_id in coordinator.data.keys()}
    
    # Find all devices registered for this config entry
    devices_to_remove: list[str] = []
    
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        # Check if any of the device identifiers match our domain
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                if device_id not in current_device_ids:
                    devices_to_remove.append(device_entry.name or device_id)
                    
                    # Remove the device (this also removes all associated entities)
                    device_registry.async_remove_device(device_entry.id)
                    LOGGER.info("Removed stale device: %s (ID: %s)", device_entry.name, device_id)
                break
    
    # Create an issue if devices were removed
    if devices_to_remove:
        async_create_issue(
            hass,
            DOMAIN,
            f"{entry.entry_id}_devices_removed",
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key="devices_removed",
            translation_placeholders={"devices": ", ".join(devices_to_remove)},
        )