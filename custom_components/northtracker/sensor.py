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
                LOGGER.debug("Discovering sensors for new device: %s (ID: %d)", device.name, device_id)
                
                # Add standard device sensors ONLY for the main GPS tracker device
                # (not for virtual Bluetooth sensor devices)
                if hasattr(device, 'available_bluetooth_sensors'):
                    # This is a main GPS tracker device, add standard sensors
                    for description in SENSOR_DESCRIPTIONS:
                        sensor_entity = NorthTrackerSensor(coordinator, device.id, description)
                        new_entities.append(sensor_entity)
                        LOGGER.debug("Created sensor: %s for device %s", description.key, device.name)
                    
                    # Add dynamic Bluetooth sensors for this main device
                    for bt_sensor in device.available_bluetooth_sensors:
                        serial_number = bt_sensor["serial_number"]
                        sensor_name = bt_sensor["name"]
                        
                        # Temperature sensor
                        if bt_sensor["enable_temperature"]:
                            temp_entity = NorthTrackerBluetoothSensor(
                                coordinator, device.id, serial_number, "temperature", sensor_name
                            )
                            new_entities.append(temp_entity)
                            LOGGER.debug("Created Bluetooth temperature sensor for %s (%s)", sensor_name, serial_number)
                        
                        # Humidity sensor  
                        if bt_sensor["enable_humidity"]:
                            humidity_entity = NorthTrackerBluetoothSensor(
                                coordinator, device.id, serial_number, "humidity", sensor_name
                            )
                            new_entities.append(humidity_entity)
                            LOGGER.debug("Created Bluetooth humidity sensor for %s (%s)", sensor_name, serial_number)
                        
                        # Battery percentage sensor
                        if bt_sensor["has_data"]:  # Only create if we have data
                            battery_entity = NorthTrackerBluetoothSensor(
                                coordinator, device.id, serial_number, "battery_percentage", sensor_name
                            )
                            new_entities.append(battery_entity)
                            LOGGER.debug("Created Bluetooth battery sensor for %s (%s)", sensor_name, serial_number)
                            
                            # Battery voltage sensor
                            battery_voltage_entity = NorthTrackerBluetoothSensor(
                                coordinator, device.id, serial_number, "battery_voltage", sensor_name
                            )
                            new_entities.append(battery_voltage_entity)
                            LOGGER.debug("Created Bluetooth battery voltage sensor for %s (%s)", sensor_name, serial_number)
                            
                            # Last seen sensor
                            last_seen_entity = NorthTrackerBluetoothSensor(
                                coordinator, device.id, serial_number, "last_seen", sensor_name
                            )
                            new_entities.append(last_seen_entity)
                            LOGGER.debug("Created Bluetooth last seen sensor for %s (%s)", sensor_name, serial_number)
                
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

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int, 
                 serial_number: str, sensor_type: str, sensor_name: str) -> None:
        """Initialize the Bluetooth sensor."""
        super().__init__(coordinator, device_id)
        self._serial_number = serial_number
        self._sensor_type = sensor_type
        self._sensor_name = sensor_name
        
        # Build unique ID and entity ID
        self._attr_unique_id = f"{self._device_id}_{serial_number}_{sensor_type}"
        
        # Set sensor properties based on type
        if sensor_type == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
            self._attr_icon = "mdi:thermometer"
            self._attr_name = f"{sensor_name} Temperature"
            self._attr_translation_key = "bluetooth_temperature"
            
        elif sensor_type == "humidity":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 0
            self._attr_icon = "mdi:water-percent"
            self._attr_name = f"{sensor_name} Humidity"
            self._attr_translation_key = "bluetooth_humidity"
            
        elif sensor_type == "battery_percentage":
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 0
            self._attr_icon = "mdi:battery"
            self._attr_name = f"{sensor_name} Battery"
            self._attr_translation_key = "bluetooth_battery_percentage"
            
        elif sensor_type == "battery_voltage":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 3
            self._attr_icon = "mdi:battery-high"
            self._attr_name = f"{sensor_name} Battery Voltage"
            self._attr_translation_key = "bluetooth_battery_voltage"
            
        elif sensor_type == "last_seen":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_icon = "mdi:clock-outline"
            self._attr_name = f"{sensor_name} Last Seen"
            self._attr_translation_key = "bluetooth_last_seen"
        
        # All Bluetooth sensors are diagnostic
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
        if self._sensor_type == "temperature":
            value = device.get_bluetooth_sensor_temperature(self._serial_number)
        elif self._sensor_type == "humidity":
            value = device.get_bluetooth_sensor_humidity(self._serial_number)
        elif self._sensor_type == "battery_percentage":
            value = device.get_bluetooth_sensor_battery_percentage(self._serial_number)
        elif self._sensor_type == "battery_voltage":
            value = device.get_bluetooth_sensor_battery_voltage(self._serial_number)
        elif self._sensor_type == "last_seen":
            value = device.get_bluetooth_sensor_last_seen(self._serial_number)
        else:
            LOGGER.warning("Unknown Bluetooth sensor type: %s", self._sensor_type)
            return None
        
        LOGGER.debug("Bluetooth sensor %s (%s) for device %s returning value: %s", 
                    self._sensor_type, self._serial_number, device.name, value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes for Bluetooth sensor."""
        attributes = super().extra_state_attributes or {}
        attributes.update({
            "serial_number": self._serial_number,
            "sensor_name": self._sensor_name,
            "sensor_type": self._sensor_type,
        })
        return attributes