"""Base entity for the NorthTracker integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base import validate_device_name
from .const import CONFIGURATION_URL, DOMAIN, MANUFACTURER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .devices import NorthTrackerBaseDevice, NorthTrackerSensorDevice


def _build_device_info(device: NorthTrackerBaseDevice) -> DeviceInfo:
    """Return the device info for a device, using the IMEI as stable identifier."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.imei)},
        name=validate_device_name(device.name),
        manufacturer=MANUFACTURER,
        model=device.model,
        serial_number=device.imei,
        configuration_url=CONFIGURATION_URL,
    )


class NorthTrackerEntity(CoordinatorEntity[NorthTrackerDataUpdateCoordinator]):
    """Defines a base NorthTracker entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int
    ) -> None:
        """Initialize the NorthTracker entity."""
        super().__init__(coordinator)
        self._device_id = device_id

        device = self.device
        if device:
            device_info = _build_device_info(device)

            # Link Bluetooth sensors to their parent GPS device. via_device_id needs
            # the parent's registry id, so make sure the parent is registered first;
            # it may not be yet when its entities live on a platform set up later.
            if isinstance(device, NorthTrackerSensorDevice):
                parent_entry = dr.async_get(coordinator.hass).async_get_or_create(
                    config_entry_id=coordinator.config_entry.entry_id,
                    **_build_device_info(device.parent_device),
                )
                device_info["via_device_id"] = parent_entry.id

            self._attr_device_info = device_info
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(device_id))},
                name=f"NorthTracker Device {device_id}",
                manufacturer=MANUFACTURER,
            )

    @property
    def device(self) -> NorthTrackerBaseDevice | None:
        """Return the device object for this entity."""
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.device
        if device is None:
            return False
        return self.coordinator.last_update_success and device.available
