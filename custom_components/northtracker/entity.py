"""Base entity for the North-Tracker integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .api import NorthTrackerDevice


class NorthTrackerEntity(CoordinatorEntity[NorthTrackerDataUpdateCoordinator]):
    """Defines a base North-Tracker entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int) -> None:
        """Initialize the North-Tracker entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        LOGGER.debug("Initializing entity for device ID %d", device_id)
        
        # Get device info for logging
        if device_id in coordinator.data:
            device = coordinator.data[device_id]
            LOGGER.debug("Entity initialized for device: %s (ID: %d, Model: %s)", 
                        device.name, device.id, device.model)
        else:
            LOGGER.warning("Device ID %d not found in coordinator data during entity init", device_id)
        
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
        if self._device_id not in self.coordinator.data:
            LOGGER.warning("Device ID %d not found in coordinator data", self._device_id)
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        is_available = self.coordinator.last_update_success and self.device.available
        if not is_available:
            LOGGER.debug("Entity for device %s not available: coordinator_success=%s, device_available=%s", 
                        self.device.name if self._device_id in self.coordinator.data else self._device_id,
                        self.coordinator.last_update_success, 
                        self.device.available if self._device_id in self.coordinator.data else False)
        return is_available