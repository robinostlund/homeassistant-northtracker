"""Binary sensor platform for North-Tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .api import NorthTrackerGpsDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a North-Tracker binary sensor entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerGpsDevice], Any] | None = None
    exists_fn: Callable[[NorthTrackerGpsDevice], bool] | None = None

# Unified binary sensor descriptions for both main GPS devices and Bluetooth sensors
BINARY_SENSOR_DESCRIPTIONS: tuple[NorthTrackerBinarySensorEntityDescription, ...] = (
    # GPS/tracker device binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="bluetooth_enabled",
        translation_key="bluetooth_enabled",
        # device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:bluetooth",
        value_fn=lambda device: device.bluetooth_enabled,
        exists_fn=lambda device: hasattr(device, 'bluetooth_enabled') and device.bluetooth_enabled is not None,
    ),
    # Bluetooth sensor binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="magnetic_contact",
        translation_key="magnetic_contact",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:magnet",
        value_fn=lambda device: device.magnetic_contact_open,
        exists_fn=lambda device: hasattr(device, 'magnetic_contact_open') and device.magnetic_contact_open is not None,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the binary sensor platform and discover new entities."""
    from .base import BasePlatformSetup
    
    def create_binary_sensor_entity(coordinator, device_id, description):
        """Create a binary sensor entity instance."""
        return NorthTrackerBinarySensor(coordinator, device_id, description)
    
    # Use the generic platform setup helper
    platform_setup = BasePlatformSetup(
        platform_name="binary_sensor",
        entity_class=NorthTrackerBinarySensor,
        entity_descriptions=BINARY_SENSOR_DESCRIPTIONS,
        create_entity_callback=create_binary_sensor_entity
    )
    
    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a North-Tracker binary sensor for both GPS and Bluetooth devices."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: NorthTrackerBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = validate_entity_id(f"{device_id}_{description.key}")

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if not self.available:
            LOGGER.debug("Binary sensor %s not available", self.entity_description.key)
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Binary sensor %s device is None", self.entity_description.key)
            return None
            
        # Use value_fn from entity description
        if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
            state = self.entity_description.value_fn(device)
        else:
            # Fallback to getattr for backwards compatibility
            state = getattr(device, self.entity_description.key, None)
            
        LOGGER.debug("Binary sensor %s for device %s has state: %s", self.entity_description.key, device.name, state)
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes or {}
        
        # Add binary sensor-specific attributes
        if hasattr(self, 'entity_description'):
            attributes["sensor_type"] = self.entity_description.key
        
        return attributes if attributes else None

