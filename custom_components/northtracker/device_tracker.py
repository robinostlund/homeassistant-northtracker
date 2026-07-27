"""Device tracker platform for NorthTracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import (
    SourceType,
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NorthTrackerConfigEntry, NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity

# All data comes from the coordinator, so there is no per-entity polling to limit.
PARALLEL_UPDATES = 0

# Device tracker entity description
DEVICE_TRACKER_DESCRIPTION = TrackerEntityDescription(
    key="location",
    translation_key="location",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NorthTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    """Defines a NorthTracker device tracker."""

    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: TrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        # Use IMEI for stable unique_id
        device = self.device
        identifier = device.imei if device else str(device_id)
        self._attr_unique_id = f"{identifier}_tracker"

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
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if not self.available or not self._has_valid_position:
            return 0
        return getattr(self.device, "gps_accuracy", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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

        return attributes or None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only trigger update if this device has actual data changes
        if self.coordinator.device_has_changes(self._device_id):
            super()._handle_coordinator_update()
