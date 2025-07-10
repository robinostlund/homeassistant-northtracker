"""Base entity for the North-Tracker integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorthTrackerDataUpdateCoordinator
from .api import NorthTrackerDevice


class NorthTrackerEntity(CoordinatorEntity[NorthTrackerDataUpdateCoordinator]):
    """Defines a base North-Tracker entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int) -> None:
        """Initialize the North-Tracker entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.device.id))},
            name=self.device.name,
            manufacturer="North-Tracker",
            model=self.device.model,
            serial_number=self.device.imei,
        )

    @property
    def device(self) -> NorthTrackerDevice:
        """Return the device object for this entity."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.device.available