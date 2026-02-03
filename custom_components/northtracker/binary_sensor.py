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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .devices import NorthTrackerBaseDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a North-Tracker binary sensor entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerBaseDevice], Any] | None = None


# Unified binary sensor descriptions for both main GPS devices and Bluetooth sensors
BINARY_SENSOR_DESCRIPTIONS: tuple[NorthTrackerBinarySensorEntityDescription, ...] = (
    # GPS/tracker device binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="bluetooth_enabled",
        translation_key="bluetooth_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.bluetooth_enabled,
    ),
    # Bluetooth sensor binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="door_sensor",
        translation_key="door_sensor",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda device: not device.magnetic_contact,  # Invert: True=closed->False, False=open->True
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
            return None
            
        device = self.device
        if device is None:
            return None
            
        # Use value_fn from entity description
        if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
            return self.entity_description.value_fn(device)
        return getattr(device, self.entity_description.key, None)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        # Use base class attributes only
        return super().extra_state_attributes

