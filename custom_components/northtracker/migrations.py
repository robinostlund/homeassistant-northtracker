"""Migration utilities for North-Tracker integration."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from .coordinator import NorthTrackerDataUpdateCoordinator

# Current schema version - increment when making breaking changes
CURRENT_SCHEMA_VERSION = 2

# Schema version history:
# 1: Initial version - used device_id for unique_id (e.g., "66131_temperature")
# 2: Changed to IMEI for unique_id (e.g., "864275072937959_temperature")


async def async_migrate_entry_if_needed(
    hass: HomeAssistant,
    coordinator: "NorthTrackerDataUpdateCoordinator",
) -> None:
    """Migrate entity unique_ids if needed.
    
    This function checks if entities need migration from the old device_id-based
    unique_ids to the new IMEI-based unique_ids.
    """
    entity_registry = er.async_get(hass)
    
    # Build a mapping of device_id -> imei from current coordinator data
    device_id_to_imei: dict[int, str] = {}
    for device_id, device in coordinator.data.items():
        if hasattr(device, 'imei') and device.imei:
            device_id_to_imei[device_id] = device.imei
    
    if not device_id_to_imei:
        LOGGER.debug("No devices found for migration")
        return
    
    LOGGER.debug("Starting entity unique_id migration check. Device mappings: %s", 
                {k: v[:6] + "..." for k, v in device_id_to_imei.items()})
    
    migrated_count = 0
    
    # Find all entities for this integration
    entities = er.async_entries_for_config_entry(
        entity_registry, 
        coordinator.config_entry.entry_id
    )
    
    for entity in entities:
        old_unique_id = entity.unique_id
        
        # Check if this looks like an old-style unique_id (starts with device_id)
        # Pattern: "12345_sensor_key" where 12345 is the device_id
        match = re.match(r'^(\d+)_(.+)$', old_unique_id)
        if not match:
            continue
            
        potential_device_id = int(match.group(1))
        entity_suffix = match.group(2)
        
        # Check if this device_id exists in our mapping
        if potential_device_id not in device_id_to_imei:
            # Could be already migrated (IMEI looks like a number too)
            # Check if the potential_device_id is actually an IMEI (typically 15 digits)
            if len(str(potential_device_id)) >= 14:
                # Already using IMEI format, skip
                continue
            # Unknown device, skip
            continue
        
        imei = device_id_to_imei[potential_device_id]
        new_unique_id = f"{imei}_{entity_suffix}"
        
        # Don't migrate if already using the new format
        if old_unique_id == new_unique_id:
            continue
        
        # Check if an entity with the new unique_id already exists
        existing = entity_registry.async_get_entity_id(
            entity.domain, DOMAIN, new_unique_id
        )
        if existing:
            LOGGER.warning(
                "Cannot migrate entity %s: entity with new unique_id %s already exists",
                entity.entity_id, new_unique_id
            )
            continue
        
        # Perform the migration
        try:
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=new_unique_id
            )
            LOGGER.info(
                "Migrated entity %s unique_id: %s -> %s",
                entity.entity_id, old_unique_id, new_unique_id
            )
            migrated_count += 1
        except Exception as err:
            LOGGER.error(
                "Failed to migrate entity %s: %s",
                entity.entity_id, err
            )
    
    if migrated_count > 0:
        LOGGER.info("Successfully migrated %d entity unique_ids to IMEI format", migrated_count)
    else:
        LOGGER.debug("No entities needed migration")


def get_unique_id(imei: str, key: str) -> str:
    """Generate a unique_id using IMEI.
    
    Args:
        imei: The device IMEI (or serial number for Bluetooth sensors)
        key: The entity key (e.g., "temperature", "tracker")
        
    Returns:
        Formatted unique_id string
    """
    return f"{imei}_{key}"
