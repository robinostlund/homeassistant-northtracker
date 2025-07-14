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
        device = self.device
        if device:
            LOGGER.debug("Entity initialized for device: %s (ID: %d, Model: %s)", 
                        device.name, device.id, device.model)
            
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device.id))},
                name=device.name,
                manufacturer="North-Tracker",
                model=device.model,
                serial_number=device.imei,
            )
        else:
            LOGGER.warning("Device ID %d not found in coordinator data during entity init", device_id)
            # Create minimal device info
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device_id))},
                name=f"North-Tracker Device {device_id}",
                manufacturer="North-Tracker",
            )

    @property
    def device(self) -> NorthTrackerDevice | None:
        """Return the device object for this entity."""
        if self._device_id not in self.coordinator.data:
            LOGGER.warning("Device ID %d not found in coordinator data", self._device_id)
            return None
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.device
        if device is None:
            LOGGER.debug("Entity for device ID %d not available: device not found in coordinator data", self._device_id)
            return False
        
        is_available = self.coordinator.last_update_success and device.available
        if not is_available:
            LOGGER.debug("Entity for device %s not available: coordinator_success=%s, device_available=%s", 
                        device.name, self.coordinator.last_update_success, device.available)
        return is_available