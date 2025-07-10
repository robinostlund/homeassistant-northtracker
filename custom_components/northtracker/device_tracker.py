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

from .const import DOMAIN
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the device tracker platform and discover new entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    added_devices = set()

    def discover_trackers() -> None:
        """Discover and add new tracker entities."""
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                # Create a tracker for every device, it will just not have a state if no position is available
                new_entities.append(NorthTrackerDeviceTracker(coordinator, device.id))
                added_devices.add(device_id)

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(discover_trackers))
    discover_trackers()


class NorthTrackerDeviceTracker(NorthTrackerEntity, TrackerEntity):
    """Defines a North-Tracker device tracker."""

    # This tells the entity to use the "location" key from our translation files for its name.
    _attr_translation_key = "location"

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{self._device_id}_tracker"

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if not self.available:
            return None
        return self.device.latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if not self.available:
            return None
        return self.device.longitude

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if not self.available:
            return 0
        return self.device.gps_accuracy

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return extra state attributes."""
        if not self.available:
            return None
            
        attributes = {}
        
        # Only include valid attributes
        if self.device.speed is not None:
            attributes["speed"] = self.device.speed
        if self.device.course is not None:
            attributes["course"] = self.device.course
        if self.device.last_seen:
            attributes["last_seen"] = self.device.last_seen
        if self.device.has_position:
            attributes["has_position"] = True
            if self.device.gps_accuracy > 0:
                attributes["gps_accuracy"] = self.device.gps_accuracy
                
        return attributes if attributes else None