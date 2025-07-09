"""Device tracker platform for North-Tracker."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
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

    _attr_name = None  # The device name is used as the entity name

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
        return self.device.latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.device.longitude

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        return self.device.gps_accuracy

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return extra state attributes."""
        return {
            "speed": self.device.speed,
            "course": self.device.course,
            "last_seen": self.device.last_seen,
        }