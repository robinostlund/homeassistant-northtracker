"""Base entity for the North-Tracker integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .api import NorthTrackerGpsDevice
from .base import validate_device_name


class NorthTrackerEntity(CoordinatorEntity[NorthTrackerDataUpdateCoordinator]):
    """Defines a base North-Tracker entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int) -> None:
        """Initialize the North-Tracker entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        LOGGER.debug("Initializing entity for device ID %s", device_id)
        
        # Get device info for logging
        device = self.device
        if device:
            LOGGER.debug("Entity initialized for device: %s (ID: %s, Model: %s)", 
                        device.name, device.id, device.model)
            
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device.id))},
                name=validate_device_name(device.name),
                manufacturer="North-Tracker",
                model=device.model,
                serial_number=device.imei,
            )
        else:
            LOGGER.warning("Device ID %s not found in coordinator data during entity init", device_id)
            # Create minimal device info
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device_id))},
                name=f"North-Tracker Device {device_id}",
                manufacturer="North-Tracker",
            )

    @property
    def device(self) -> NorthTrackerGpsDevice | None:
        """Return the device object for this entity."""
        if self._device_id not in self.coordinator.data:
            LOGGER.warning("Device ID %s not found in coordinator data", self._device_id)
            return None
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.device
        if device is None:
            LOGGER.debug("Entity for device ID %s not available: device not found in coordinator data", self._device_id)
            return False
        
        is_available = self.coordinator.last_update_success and device.available
        if not is_available:
            LOGGER.debug("Entity for device %s not available: coordinator_success=%s, device_available=%s", 
                        device.name, self.coordinator.last_update_success, device.available)
        return is_available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes common to all North-Tracker entities."""
        device = self.device
        if device is None:
            return None
        
        attributes = {}
        
        # Common device attributes that all entities can benefit from
        if hasattr(device, 'device_type') and device.device_type:
            attributes["device_type"] = device.device_type
            
        if hasattr(device, 'serial_number') and device.serial_number:
            attributes["serial_number"] = device.serial_number
            
        # Include last seen for all entities that have it
        if hasattr(device, 'last_seen') and device.last_seen:
            attributes["last_seen"] = device.last_seen
        
        # For GPS devices, include basic location info
        if hasattr(device, 'has_position'):
            attributes["has_position"] = device.has_position
            
        # For Bluetooth devices, include connection info  
        if hasattr(device, 'device_type') and device.device_type == "bluetooth_sensor":
            # Bluetooth sensors are connected through their parent GPS device
            if hasattr(device, 'parent_device'):
                parent = device.parent_device
                if hasattr(parent, 'has_position'):
                    attributes["parent_has_position"] = parent.has_position
        
        return attributes if attributes else None