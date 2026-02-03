"""Base entity for the North-Tracker integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, CONFIGURATION_URL
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
                manufacturer=MANUFACTURER,
                model=device.model,
                serial_number=device.imei,
                configuration_url=CONFIGURATION_URL,
            )
            
            # Add via_device for Bluetooth sensors to link them to their parent GPS device
            if isinstance(device, NorthTrackerSensorDevice) and hasattr(device, 'parent_device'):
                device_info["via_device"] = (DOMAIN, str(device.parent_device.id))
            
            self._attr_device_info = device_info
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device_id))},
                name=f"North-Tracker Device {device_id}",
                manufacturer=MANUFACTURER,
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