"""Base entity for the North-Tracker integration."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorthTrackerDataUpdateCoordinator
from .api import NorthTrackerDevice

class NorthTrackerEntity(CoordinatorEntity[NorthTrackerDataUpdateCoordinator]):
    """Defines a base North-Tracker entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device: NorthTrackerDevice):
        """Initialize the North-Tracker entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.device.id))},
            name=self.device.name,
            manufacturer="North-Tracker",
            model=self.device.model,
            sw_version=self.device.device_type,
        )