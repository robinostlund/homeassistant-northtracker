"""Sensor platform for North-Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        icon= "mdi:battery",
    ),
    SensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key="gps_signal",
        translation_key="gps_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="network_signal",
        translation_key="network_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="speed",
        translation_key="speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        suggested_display_precision=0,
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="report_frequency",
        translation_key="report_frequency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter",
    ),
)

# Bluetooth sensor descriptions
BLUETOOTH_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        translation_key="bluetooth_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="bluetooth_humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        suggested_display_precision=0,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="battery_percentage",
        translation_key="bluetooth_battery_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=0,
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_voltage",
        translation_key="bluetooth_battery_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_seen",
        translation_key="bluetooth_last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-outline",
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the sensor platform and discover new entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    added_devices = set()

    def discover_sensors() -> None:
        """Discover and add new sensors."""
        LOGGER.debug("Starting sensor discovery, current devices: %d", len(coordinator.data))
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                LOGGER.debug("Discovering sensors for new device: %s (ID: %s)", device.name, device_id)
                LOGGER.debug("Device type: %s, Name: %s", device.device_type, device.name)
                
                # Handle different device types
                if device.device_type == "bluetooth_sensor":
                    # This is a virtual Bluetooth sensor device
                    LOGGER.debug("Adding Bluetooth sensors for device: %s", device.name)
                    bt_data = device.sensor_data
                    
                    # Create sensors based on descriptions and availability
                    for description in BLUETOOTH_SENSOR_DESCRIPTIONS:
                        should_create = False
                        
                        # Check if this sensor type should be created
                        if description.key == "temperature" and bt_data.get("enable_temperature", False):
                            should_create = True
                        elif description.key == "humidity" and bt_data.get("enable_humidity", False):
                            should_create = True
                        elif description.key in ["battery_percentage", "battery_voltage", "last_seen"] and bt_data.get("has_data", False):
                            should_create = True
                        
                        if should_create:
                            sensor_entity = NorthTrackerBluetoothSensor(coordinator, device_id, description)
                            new_entities.append(sensor_entity)
                            LOGGER.debug("Created Bluetooth sensor: %s for device %s", description.key, device.name)
                
                elif device.device_type in ["gps", "tracker"]:
                    # This is a main GPS tracker device - add standard sensors only
                    LOGGER.debug("Adding standard sensors for GPS device: %s", device.name)
                    for description in SENSOR_DESCRIPTIONS:
                        sensor_entity = NorthTrackerSensor(coordinator, device.id, description)
                        new_entities.append(sensor_entity)
                        LOGGER.debug("Created sensor: %s for device %s", description.key, device.name)
                
                else:
                    LOGGER.debug("Skipping sensor creation for device: %s (type: %s) - unknown device type", 
                               device.name, device.device_type)
                
                added_devices.add(device_id)
        
        if new_entities:
            LOGGER.debug("Adding %d new sensor entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new sensor entities to add")

    entry.async_on_unload(coordinator.async_add_listener(discover_sensors))
    discover_sensors()


class NorthTrackerSensor(NorthTrackerEntity, SensorEntity):
    """Defines a North-Tracker sensor."""

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.available:
            LOGGER.debug("Sensor %s not available", self.entity_description.key)
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Sensor %s device is None", self.entity_description.key)
            return None
            
        value = getattr(device, self.entity_description.key, None)
        LOGGER.debug("Sensor %s for device %s has raw value: %s", self.entity_description.key, device.name, value)
        
        # Validate the value based on the sensor type
        if value is None:
            LOGGER.debug("Sensor %s for device %s has None value", self.entity_description.key, device.name)
            return None
            
        # Additional validation for specific sensor types
        if self.entity_description.key == "battery_voltage" and isinstance(value, (int, float)):
            # Battery voltage should be reasonable (0-50V for most vehicles)
            if not (0 <= value <= 50):
                LOGGER.warning("Battery voltage out of range for device %s: %s", device.name, value)
                return None
        elif self.entity_description.key in ["gps_signal", "network_signal"] and isinstance(value, (int, float)):
            # Signal strength should be 0-100 percent
            if not (0 <= value <= 100):
                LOGGER.warning("Signal strength out of range for device %s (%s): %s", device.name, self.entity_description.key, value)
                return None
        elif self.entity_description.key == "network_signal" and not device.has_position:
            # Network signal should only be available when device has GPS data
            LOGGER.debug("Network signal unavailable for device %s - no GPS position data", device.name)
            return None
        
        LOGGER.debug("Sensor %s for device %s returning validated value: %s", self.entity_description.key, device.name, value)
        return value


class NorthTrackerBluetoothSensor(NorthTrackerEntity, SensorEntity):
    """Defines a North-Tracker Bluetooth sensor."""

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: str, 
                 description: SensorEntityDescription) -> None:
        """Initialize the Bluetooth sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        
        # Get Bluetooth device info
        device = self.device
        if device:
            self._sensor_name = device.name
            self._serial_number = device.serial_number
        else:
            self._sensor_name = "Unknown Bluetooth Sensor"
            self._serial_number = "unknown"
        
        # Build unique ID and entity ID
        self._attr_unique_id = f"{device_id}_{description.key}"
        # Don't set _attr_name manually - let Home Assistant combine device name + entity description
        # since _attr_has_entity_name = True in the base class

    @property
    def native_value(self) -> StateType:
        """Return the state of the Bluetooth sensor."""
        if not self.available:
            LOGGER.debug("Bluetooth sensor %s not available", self._attr_unique_id)
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Bluetooth sensor %s device is None", self._attr_unique_id)
            return None
        
        # Get the appropriate value based on sensor type
        sensor_key = self.entity_description.key
        if sensor_key == "temperature":
            value = device.temperature
        elif sensor_key == "humidity":
            value = device.humidity
        elif sensor_key == "battery_percentage":
            value = device.battery_percentage
        elif sensor_key == "battery_voltage":
            value = device.battery_voltage
        elif sensor_key == "last_seen":
            value = device.last_seen
        else:
            LOGGER.warning("Unknown Bluetooth sensor type: %s", sensor_key)
            return None
        
        LOGGER.debug("Bluetooth sensor %s for device %s returning value: %s", 
                    sensor_key, device.name, value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes for Bluetooth sensor."""
        attributes = super().extra_state_attributes or {}
        attributes.update({
            "serial_number": self._serial_number,
            "sensor_name": self._sensor_name,
            "sensor_type": self.entity_description.key,
        })
        return attributes