"""The NorthTracker integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import NorthTrackerConfigEntry, NorthTrackerDataUpdateCoordinator
from .migrations import async_migrate_entry_if_needed


async def async_setup_entry(
    hass: HomeAssistant, entry: NorthTrackerConfigEntry
) -> bool:
    """Set up NorthTracker from a config entry."""
    coordinator = NorthTrackerDataUpdateCoordinator(hass, entry)

    # async_config_entry_first_refresh raises ConfigEntryNotReady / ConfigEntryAuthFailed
    # itself, so we must not wrap it and accidentally convert an auth failure into a
    # retry (which would break the reauth flow).
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Migrate entity unique_ids from old format (device_id) to new format (IMEI)
    await async_migrate_entry_if_needed(hass, coordinator)

    # Clean up stale devices and entities
    await async_cleanup_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when its options (e.g. scan interval) change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Clear any previous issues since setup was successful
    ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_api_error")
    ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_rate_limit")

    LOGGER.info("NorthTracker integration setup completed for %s", entry.title)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NorthTrackerConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        try:
            if coordinator.api.is_authenticated:
                await coordinator.api.logout()
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Error during logout: %s", err)

        LOGGER.info("NorthTracker integration unloaded for %s", entry.title)
    else:
        LOGGER.error("Failed to unload platforms for NorthTracker integration")

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: NorthTrackerConfigEntry
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: NorthTrackerConfigEntry,
    coordinator: NorthTrackerDataUpdateCoordinator,
) -> None:
    """Remove devices and entities that no longer exist in the API."""
    # Never delete anything based on a partial device list. A failing endpoint
    # (for example real-time tracking, which is where Bluetooth sensors come
    # from) would otherwise permanently remove those devices and their entities.
    if coordinator.update_degraded:
        LOGGER.warning(
            "Skipping stale device cleanup: the last update was incomplete, "
            "so the device list cannot be trusted"
        )
        return

    if not coordinator.data:
        LOGGER.debug("Skipping stale device cleanup: no devices returned by the API")
        return

    device_registry = dr.async_get(hass)

    # Get current device IMEIs from the API (identifiers are now IMEI-based)
    current_imeis = {
        device.imei
        for device in coordinator.data.values()
        if hasattr(device, "imei") and device.imei
    }

    # Find all devices registered for this config entry
    devices_to_remove: list[str] = []

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        # Check if any of the device identifiers match our domain
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_identifier = identifier[1]
                if device_identifier not in current_imeis:
                    devices_to_remove.append(device_entry.name or device_identifier)

                    # Remove the device (this also removes all associated entities)
                    device_registry.async_remove_device(device_entry.id)
                    LOGGER.info(
                        "Removed stale device: %s (ID: %s)",
                        device_entry.name,
                        device_identifier,
                    )
                break

    # Create an issue if devices were removed
    if devices_to_remove:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{entry.entry_id}_devices_removed",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="devices_removed",
            translation_placeholders={"devices": ", ".join(devices_to_remove)},
        )
