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
from .api import NorthTrackerDevice


@dataclass(kw_only=True)
class NorthTrackerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a North-Tracker binary sensor entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerDevice], Any] | None = None
    exists_fn: Callable[[NorthTrackerDevice], bool] | None = None

# Unified binary sensor descriptions for both main GPS devices and Bluetooth sensors
BINARY_SENSOR_DESCRIPTIONS: tuple[NorthTrackerBinarySensorEntityDescription, ...] = (
    # GPS/tracker device binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="bluetooth_enabled",
        translation_key="connection",
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
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    added_devices = set()

    def discover_binary_sensors() -> None:
        """Discover and add new binary sensors."""
        LOGGER.debug("Starting binary sensor discovery, current devices: %d", len(coordinator.data))
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                LOGGER.debug("Discovering binary sensors for new device: %s (ID: %s)", device.name, device_id)
                
                # Use unified binary sensor descriptions for all device types
                for description in BINARY_SENSOR_DESCRIPTIONS:
                    if description.exists_fn and description.exists_fn(device):
                        # Create binary sensor entity - exists_fn already determined capability
                        binary_sensor_entity = NorthTrackerBinarySensor(coordinator, device_id, description)
                        new_entities.append(binary_sensor_entity)
                        LOGGER.debug("Created binary sensor: %s for device %s", description.key, device.name)
                
                added_devices.add(device_id)

        if new_entities:
            LOGGER.debug("Adding %d new binary sensor entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new binary sensor entities to add")

    entry.async_on_unload(coordinator.async_add_listener(discover_binary_sensors))
    discover_binary_sensors()


class NorthTrackerBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a North-Tracker binary sensor for both GPS and Bluetooth devices."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int | str, 
        description: NorthTrackerBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

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

