"""Binary sensor platform for North-Tracker."""
from __future__ import annotations

from typing import Any

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
                
                # Add static binary sensors ONLY for the main GPS tracker device
                # (not for virtual Bluetooth sensor devices)
                if hasattr(device, 'available_bluetooth_sensors'):
                    # This is a main GPS tracker device, add static binary sensors
                    for description in STATIC_BINARY_SENSOR_DESCRIPTIONS:
                        if hasattr(device, description.key):
                            binary_sensor_entity = NorthTrackerBinarySensor(coordinator, device.id, description)
                            new_entities.append(binary_sensor_entity)
                            LOGGER.debug("Created static binary sensor: %s for device %s", description.key, device.name)
                        else:
                            LOGGER.debug("Device %s does not have attribute %s, skipping binary sensor", device.name, description.key)
                    
                    # Add dynamic Bluetooth binary sensors for this main device
                    for bt_sensor in device.available_bluetooth_sensors:
                        serial_number = bt_sensor["serial_number"]
                        sensor_name = bt_sensor["name"]
                        
                        # Door/Magnetic field sensor
                        if bt_sensor["enable_door_sensor"] and bt_sensor["has_data"]:
                            door_entity = NorthTrackerBluetoothBinarySensor(
                                coordinator, device.id, serial_number, "magnetic_field", sensor_name
                            )
                            new_entities.append(door_entity)
                            LOGGER.debug("Created Bluetooth door/magnetic field sensor for %s (%s)", sensor_name, serial_number)
                
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
            LOGGER.debug("Binary sensor %s not available", self.entity_description.key)
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Binary sensor %s device is None", self.entity_description.key)
            return None
            
        # Property-based sensor (like bluetooth_enabled)
        state = getattr(device, self.entity_description.key, None)
            
        LOGGER.debug("Binary sensor %s for device %s has state: %s", self.entity_description.key, device.name, state)
        return state


class NorthTrackerBluetoothBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a North-Tracker Bluetooth binary sensor."""

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int,
                 serial_number: str, sensor_type: str, sensor_name: str) -> None:
        """Initialize the Bluetooth binary sensor."""
        super().__init__(coordinator, device_id)
        self._serial_number = serial_number
        self._sensor_type = sensor_type
        self._sensor_name = sensor_name
        
        # Build unique ID and entity ID
        self._attr_unique_id = f"{self._device_id}_{serial_number}_{sensor_type}"
        
        # Set sensor properties based on type
        if sensor_type == "magnetic_field":
            self._attr_device_class = BinarySensorDeviceClass.DOOR
            self._attr_icon = "mdi:magnet"
            self._attr_name = f"{sensor_name} Door"
            self._attr_translation_key = "bluetooth_door"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the Bluetooth binary sensor."""
        if not self.available:
            LOGGER.debug("Bluetooth binary sensor %s not available", self._attr_unique_id)
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Bluetooth binary sensor %s device is None", self._attr_unique_id)
            return None
        
        # Get the appropriate value based on sensor type
        if self._sensor_type == "magnetic_field":
            # Note: magnetic field True = closed, False = open
            # For door sensor, we want True when door is open (reversed logic)
            magnetic_state = device.get_bluetooth_sensor_magnetic_field(self._serial_number)
            if magnetic_state is None:
                return None
            # Reverse the logic: magnetic field True (closed) -> door sensor False (closed)
            # magnetic field False (open) -> door sensor True (open)
            value = not magnetic_state
        else:
            LOGGER.warning("Unknown Bluetooth binary sensor type: %s", self._sensor_type)
            return None
        
        LOGGER.debug("Bluetooth binary sensor %s (%s) for device %s returning value: %s", 
                    self._sensor_type, self._serial_number, device.name, value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes for Bluetooth binary sensor."""
        from typing import Any
        
        attributes = super().extra_state_attributes or {}
        attributes.update({
            "serial_number": self._serial_number,
            "sensor_name": self._sensor_name,
            "sensor_type": self._sensor_type,
        })
        return attributes