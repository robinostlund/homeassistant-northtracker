"""Migration utilities for NorthTracker integration."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from .coordinator import NorthTrackerDataUpdateCoordinator

# Current schema version - increment when making breaking changes
CURRENT_SCHEMA_VERSION = 2

# Schema version history:
# 1: Initial version - used device_id for unique_id (e.g., "66131_temperature")
# 2: Changed to IMEI for unique_id and device identifiers
#    - All devices have IMEI field (GPS uses device IMEI, Bluetooth uses SerialNumber as IMEI)


async def async_migrate_entry_if_needed(
    hass: HomeAssistant,
    coordinator: "NorthTrackerDataUpdateCoordinator",
) -> None:
    """Migrate entity unique_ids and device identifiers if needed.

    This function checks if entities and devices need migration from the old
    device_id-based format to the new IMEI-based format.
    """
    # Build a mapping of device_id -> imei from current coordinator data
    device_id_to_imei: dict[int, str] = {}
    for device_id, device in coordinator.data.items():
        if hasattr(device, "imei") and device.imei:
            device_id_to_imei[device_id] = device.imei

    if not device_id_to_imei:
        LOGGER.debug("No devices found for migration")
        return

    LOGGER.debug(
        "Starting migration check. Device mappings: %s",
        {k: v[:6] + "..." for k, v in device_id_to_imei.items()},
    )

    # First migrate device registry identifiers
    await _async_migrate_device_identifiers(hass, coordinator, device_id_to_imei)

    # Then migrate entity unique_ids
    await _async_migrate_entity_unique_ids(hass, coordinator, device_id_to_imei)


async def _async_migrate_device_identifiers(
    hass: HomeAssistant,
    coordinator: "NorthTrackerDataUpdateCoordinator",
    device_id_to_imei: dict[int, str],
) -> None:
    """Migrate device identifiers from device_id to IMEI format."""
    device_registry = dr.async_get(hass)
    migrated_count = 0

    for device_id, imei in device_id_to_imei.items():
        old_identifier = (DOMAIN, str(device_id))
        new_identifier = (DOMAIN, imei)

        # Find device with old identifier
        device_entry = device_registry.async_get_device(identifiers={old_identifier})
        if device_entry is None:
            continue

        # Check if device with new identifier already exists
        existing = device_registry.async_get_device(identifiers={new_identifier})
        if existing and existing.id != device_entry.id:
            LOGGER.warning(
                "Cannot migrate device %s: device with new identifier %s already exists",
                device_id,
                imei,
            )
            continue

        # Update device identifiers
        try:
            device_registry.async_update_device(
                device_entry.id, new_identifiers={new_identifier}
            )
            LOGGER.info(
                "Migrated device identifiers: %s -> %s", old_identifier, new_identifier
            )
            migrated_count += 1
        except Exception as err:
            LOGGER.error("Failed to migrate device %s: %s", device_id, err)

    if migrated_count > 0:
        LOGGER.info(
            "Successfully migrated %d device identifiers to IMEI format", migrated_count
        )


async def _async_migrate_entity_unique_ids(
    hass: HomeAssistant,
    coordinator: "NorthTrackerDataUpdateCoordinator",
    device_id_to_imei: dict[int, str],
) -> None:
    """Migrate entity unique_ids from device_id to IMEI format."""
    entity_registry = er.async_get(hass)
    migrated_count = 0

    # Find all entities for this integration
    entities = er.async_entries_for_config_entry(
        entity_registry, coordinator.config_entry.entry_id
    )

    for entity in entities:
        old_unique_id = entity.unique_id

        # Check if this looks like an old-style unique_id (starts with device_id)
        # Pattern: "12345_sensor_key" where 12345 is the device_id
        match = re.match(r"^(\d+)_(.+)$", old_unique_id)
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
                entity.entity_id,
                new_unique_id,
            )
            continue

        # Perform the migration
        try:
            entity_registry.async_update_entity(
                entity.entity_id, new_unique_id=new_unique_id
            )
            LOGGER.info(
                "Migrated entity %s unique_id: %s -> %s",
                entity.entity_id,
                old_unique_id,
                new_unique_id,
            )
            migrated_count += 1
        except Exception as err:
            LOGGER.error("Failed to migrate entity %s: %s", entity.entity_id, err)

    if migrated_count > 0:
        LOGGER.info(
            "Successfully migrated %d entity unique_ids to IMEI format", migrated_count
        )


def get_unique_id(imei: str, key: str) -> str:
    """Generate a unique_id using IMEI.

    Args:
        imei: The device IMEI
        key: The entity key (e.g., "temperature", "tracker")

    Returns:
        Formatted unique_id string
    """
    return f"{imei}_{key}"
