"""Device tracker platform for North-Tracker."""
from __future__ import annotations

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

# Device tracker entity description
DEVICE_TRACKER_DESCRIPTION = TrackerEntityDescription(
    key="location",
    translation_key="location",
    icon="mdi:crosshairs-gps",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the device tracker platform and discover new entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    added_devices = set()

    def discover_trackers() -> None:
        """Discover and add new tracker entities."""
        LOGGER.debug("Starting device tracker discovery, current devices: %d", len(coordinator.data))
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                LOGGER.debug("Discovering tracker for new device: %s (ID: %d)", device.name, device_id)
                # Create a tracker for every device, it will just not have a state if no position is available
                tracker_entity = NorthTrackerDeviceTracker(coordinator, device.id, DEVICE_TRACKER_DESCRIPTION)
                new_entities.append(tracker_entity)
                LOGGER.debug("Created device tracker for device %s", device.name)
                added_devices.add(device_id)

        if new_entities:
            LOGGER.debug("Adding %d new device tracker entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new device tracker entities to add")

    entry.async_on_unload(coordinator.async_add_listener(discover_trackers))
    discover_trackers()


class NorthTrackerDeviceTracker(NorthTrackerEntity, TrackerEntity):
    """Defines a North-Tracker device tracker."""

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: TrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_tracker"

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if not self.available:
            LOGGER.debug("Device tracker for %s not available", self.device.name)
            return None
            
        # Only return latitude if we have a valid position
        if not self.device.has_position:
            LOGGER.debug("Device tracker for %s has no valid position", self.device.name)
            return None
            
        lat = self.device.latitude
        if lat is None:
            LOGGER.debug("Device tracker for %s latitude is None", self.device.name)
            return None
            
        LOGGER.debug("Device tracker for %s latitude: %s", self.device.name, lat)
        return lat

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if not self.available:
            LOGGER.debug("Device tracker for %s not available", self.device.name)
            return None
            
        # Only return longitude if we have a valid position
        if not self.device.has_position:
            LOGGER.debug("Device tracker for %s has no valid position", self.device.name)
            return None
            
        lon = self.device.longitude
        if lon is None:
            LOGGER.debug("Device tracker for %s longitude is None", self.device.name)
            return None
            
        LOGGER.debug("Device tracker for %s longitude: %s", self.device.name, lon)
        return lon

    @property
    def location_name(self) -> str | None:
        """Return location name when GPS coordinates are not available."""
        if not self.available:
            return "unavailable"
            
        # If we have valid GPS coordinates, don't set location_name (let HA use coordinates)
        if self.device.has_position and self.device.latitude is not None and self.device.longitude is not None:
            return None
            
        # Return a meaningful state when location is not available
        if self.device.last_seen:
            return "unknown"
        else:
            return "offline"

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if not self.available or not self.device.has_position:
            return 0
        return self.device.gps_accuracy

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return extra state attributes."""
        if not self.available:
            LOGGER.debug("Device tracker for %s not available, no attributes", self.device.name)
            return None
            
        attributes = {}
        
        # Always include position status
        attributes["has_position"] = self.device.has_position
        
        # Only include valid attributes
        if self.device.speed is not None:
            attributes["speed"] = self.device.speed
        if self.device.course is not None:
            attributes["course"] = self.device.course
        if self.device.last_seen:
            attributes["last_seen"] = self.device.last_seen
            
        # Include GPS accuracy only if we have a position
        if self.device.has_position and self.device.gps_accuracy > 0:
            attributes["gps_accuracy"] = self.device.gps_accuracy
            
        # Add location status for debugging
        if not self.device.has_position:
            if self.device.last_seen:
                attributes["location_status"] = "no_gps_fix"
            else:
                attributes["location_status"] = "offline"
        else:
            attributes["location_status"] = "active"
        
        LOGGER.debug("Device tracker for %s attributes: %s", self.device.name, attributes)
        return attributes if attributes else None

    @property
    def should_poll(self) -> bool:
        """Return False as we use coordinator for updates."""
        return False

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only trigger update if this device has actual data changes
        if self.coordinator.device_has_changes(self._device_id):
            LOGGER.debug("Updating device tracker for %s due to data changes detected by coordinator", 
                        self.device.name if self.available else self._device_id)
            super()._handle_coordinator_update()
        else:
            LOGGER.debug("Skipping device tracker update for %s - no data changes detected by coordinator", 
                        self.device.name if self.available else self._device_id)