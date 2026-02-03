"""Device tracker platform for North-Tracker."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerTrackerEntityDescription(TrackerEntityDescription):
    """Describes a North-Tracker device tracker entity."""

    pass


# Device tracker entity description
DEVICE_TRACKER_DESCRIPTION = NorthTrackerTrackerEntityDescription(
    key="location",
    translation_key="location",
)


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
        create_entity_callback=create_device_tracker_entity,
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
        # Use IMEI for stable unique_id
        device = self.device
        identifier = device.imei if device else str(device_id)
        self._attr_unique_id = validate_entity_id(f"{identifier}_tracker")

    @property
    def _has_valid_position(self) -> bool:
        """Check if device has a valid GPS position."""
        device = self.device
        if device is None:
            return False
        return (
            getattr(device, "has_position", False)
            and device.latitude is not None
            and device.longitude is not None
        )

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if not self.available or not self._has_valid_position:
            return None
        return self.device.latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if not self.available or not self._has_valid_position:
            return None
        return self.device.longitude

    @property
    def location_name(self) -> str | None:
        """Return location name when GPS coordinates are not available."""
        if not self.available:
            return "unavailable"

        device = self.device
        if device is None:
            return "unavailable"

        # If we have valid GPS coordinates, don't set location_name (let HA use coordinates)
        if self._has_valid_position:
            return None

        # Return a meaningful state when location is not available
        return "unknown" if getattr(device, "last_seen", None) else "offline"

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if not self.available or not self._has_valid_position:
            return 0
        return getattr(self.device, "gps_accuracy", 0)

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return extra state attributes."""
        if not self.available:
            return None

        device = self.device
        if device is None:
            return None

        # Start with common attributes from base class
        attributes = super().extra_state_attributes or {}

        # Course/heading is useful for tracking direction
        course = getattr(device, "course", None)
        if course is not None:
            attributes["course"] = course

        # Include GPS accuracy only if we have a position
        gps_accuracy = getattr(device, "gps_accuracy", 0)
        if self._has_valid_position and gps_accuracy > 0:
            attributes["gps_accuracy"] = gps_accuracy

        # Add location status
        has_position = self._has_valid_position
        has_last_seen = getattr(device, "last_seen", None) is not None

        if not has_position:
            attributes["location_status"] = "no_gps_fix" if has_last_seen else "offline"
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
            super()._handle_coordinator_update()
