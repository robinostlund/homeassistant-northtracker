"""Device tracker platform for North-Tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .api import NorthTrackerGpsDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerTrackerEntityDescription(TrackerEntityDescription):
    """Describes a North-Tracker device tracker entity with custom attributes."""
    
    exists_fn: Callable[[NorthTrackerGpsDevice], bool] | None = None

# Device tracker entity description
DEVICE_TRACKER_DESCRIPTION = NorthTrackerTrackerEntityDescription(
    key="location",
    translation_key="location",
    icon="mdi:crosshairs-gps",
    # Use exists_fn to determine if device should have a tracker (GPS devices only)
    exists_fn=lambda device: hasattr(device, 'device_type') and device.device_type in ["gps", "tracker"] and device.device_type is not None,
)

# Value functions for device tracker properties
def get_latitude(device) -> float | None:
    """Get latitude from device with validation."""
    if not hasattr(device, 'has_position') or not device.has_position:
        return None
    return getattr(device, 'latitude', None)

def get_longitude(device) -> float | None:
    """Get longitude from device with validation."""
    if not hasattr(device, 'has_position') or not device.has_position:
        return None
    return getattr(device, 'longitude', None)

def get_location_name(device) -> str | None:
    """Get location name when GPS coordinates are not available."""
    # If we have valid GPS coordinates, don't set location_name (let HA use coordinates)
    if (hasattr(device, 'has_position') and device.has_position and 
        hasattr(device, 'latitude') and device.latitude is not None and
        hasattr(device, 'longitude') and device.longitude is not None):
        return None
        
    # Return a meaningful state when location is not available
    if hasattr(device, 'last_seen') and device.last_seen:
        return "unknown"
    else:
        return "offline"

def get_location_accuracy(device) -> int:
    """Get location accuracy from device."""
    if not hasattr(device, 'has_position') or not device.has_position:
        return 0
    return getattr(device, 'gps_accuracy', 0)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the device tracker platform and discover new entities."""
    from .base import BasePlatformSetup
    
    def create_device_tracker_entity(coordinator, device_id, description):
        """Create a device tracker entity instance."""
        return NorthTrackerDeviceTracker(coordinator, device_id, description)
    
    # Use the generic platform setup helper with single description as list
    platform_setup = BasePlatformSetup(
        platform_name="device_tracker", 
        entity_class=NorthTrackerDeviceTracker,
        entity_descriptions=[DEVICE_TRACKER_DESCRIPTION],
        create_entity_callback=create_device_tracker_entity
    )
    
    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerDeviceTracker(NorthTrackerEntity, TrackerEntity):
    """Defines a North-Tracker device tracker."""

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: NorthTrackerTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = validate_entity_id(f"{device_id}_tracker")

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if not self.available:
            return None
            
        device = self.device
        if device is None:
            return None
            
        return get_latitude(device)

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if not self.available:
            return None
            
        device = self.device
        if device is None:
            return None
            
        return get_longitude(device)

    @property
    def location_name(self) -> str | None:
        """Return location name when GPS coordinates are not available."""
        if not self.available:
            return "unavailable"
            
        device = self.device
        if device is None:
            return "unavailable"
            
        return get_location_name(device)

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if not self.available:
            return 0
            
        device = self.device
        if device is None:
            return 0
            
        return get_location_accuracy(device)

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return extra state attributes."""
        if not self.available:
            LOGGER.debug("Device tracker not available, no attributes")
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Device tracker device is None, no attributes")
            return None
            
        # Start with common attributes from base class
        attributes = super().extra_state_attributes or {}
        
        # Add device tracker specific attributes
        if hasattr(device, 'speed') and device.speed is not None:
            attributes["speed"] = device.speed
        if hasattr(device, 'course') and device.course is not None:
            attributes["course"] = device.course
            
        # Include GPS accuracy only if we have a position
        if (hasattr(device, 'has_position') and device.has_position and 
            hasattr(device, 'gps_accuracy') and device.gps_accuracy > 0):
            attributes["gps_accuracy"] = device.gps_accuracy
            
        # Add location status for debugging
        has_position = hasattr(device, 'has_position') and device.has_position
        has_last_seen = hasattr(device, 'last_seen') and device.last_seen
        
        if not has_position:
            if has_last_seen:
                attributes["location_status"] = "no_gps_fix"
            else:
                attributes["location_status"] = "offline"
        else:
            attributes["location_status"] = "active"
        
        return attributes if attributes else None

    @property
    def should_poll(self) -> bool:
        """Return False as we use coordinator for updates."""
        return False

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only trigger update if this device has actual data changes
        if self.coordinator.device_has_changes(self._device_id):
            device = self.device
            device_name = device.name if device else f"ID {self._device_id}"
            LOGGER.debug("Updating device tracker for %s due to data changes detected by coordinator", device_name)
            super()._handle_coordinator_update()
        else:
            device = self.device
            device_name = device.name if device else f"ID {self._device_id}"
            LOGGER.debug("Skipping device tracker update for %s - no data changes detected by coordinator", device_name)