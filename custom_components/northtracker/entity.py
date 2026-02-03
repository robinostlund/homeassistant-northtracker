"""Base entity for the North-Tracker integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorthTrackerDataUpdateCoordinator
from .api import NorthTrackerGpsDevice, NorthTrackerSensorDevice
from .base import validate_device_name


class NorthTrackerEntity(CoordinatorEntity[NorthTrackerDataUpdateCoordinator]):
    """Defines a base North-Tracker entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int) -> None:
        """Initialize the North-Tracker entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        
        device = self.device
        if device:
            # Build base device info
            device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device.id))},
                name=validate_device_name(device.name),
                manufacturer="North-Tracker",
                model=device.model,
                serial_number=device.imei,
            )
            
            # Add via_device for Bluetooth sensors to link them to their parent GPS device
            if isinstance(device, NorthTrackerSensorDevice) and hasattr(device, 'parent_device'):
                device_info["via_device"] = (DOMAIN, str(device.parent_device.id))
            
            self._attr_device_info = device_info
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device_id))},
                name=f"North-Tracker Device {device_id}",
                manufacturer="North-Tracker",
            )

    @property
    def device(self) -> NorthTrackerGpsDevice | NorthTrackerSensorDevice | None:
        """Return the device object for this entity."""
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.device
        if device is None:
            return False
        return self.coordinator.last_update_success and device.available

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