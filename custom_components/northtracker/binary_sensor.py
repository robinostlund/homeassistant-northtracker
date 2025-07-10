"""Binary sensor platform for North-Tracker."""
from __future__ import annotations

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

# Static binary sensor descriptions for device features
STATIC_BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="bluetooth_enabled",
        translation_key="bluetooth",
        # device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:bluetooth",
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
                LOGGER.debug("Discovering binary sensors for new device: %s (ID: %d)", device.name, device_id)
                
                # Add static binary sensors (device features)
                for description in STATIC_BINARY_SENSOR_DESCRIPTIONS:
                    if hasattr(device, description.key):
                        binary_sensor_entity = NorthTrackerBinarySensor(coordinator, device.id, description)
                        new_entities.append(binary_sensor_entity)
                        LOGGER.debug("Created static binary sensor: %s for device %s", description.key, device.name)
                    else:
                        LOGGER.debug("Device %s does not have attribute %s, skipping binary sensor", device.name, description.key)
                
                added_devices.add(device_id)

        if new_entities:
            LOGGER.debug("Adding %d new binary sensor entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new binary sensor entities to add")

    entry.async_on_unload(coordinator.async_add_listener(discover_binary_sensors))
    discover_binary_sensors()


class NorthTrackerBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a North-Tracker binary sensor."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if not self.available:
            LOGGER.debug("Binary sensor %s for device %s is not available", self.entity_description.key, self.device.name)
            return None
            
        # Property-based sensor (like bluetooth_enabled)
        state = getattr(self.device, self.entity_description.key, None)
            
        LOGGER.debug("Binary sensor %s for device %s has state: %s", self.entity_description.key, self.device.name, state)
        return state