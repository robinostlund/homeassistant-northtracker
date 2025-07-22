"""Sensor platform for North-Tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

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

from .const import DOMAIN, LOGGER, MIN_SIGNAL_STRENGTH, MAX_SIGNAL_STRENGTH, SIGNAL_EXCELLENT_THRESHOLD, SIGNAL_GOOD_THRESHOLD, SIGNAL_POOR_THRESHOLD, MAX_BATTERY_VOLTAGE_READING
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .api import NorthTrackerGpsDevice, get_signal_quality_text
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerSensorEntityDescription(SensorEntityDescription):
    """Describes a North-Tracker sensor entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerGpsDevice], Any] | None = None
    exists_fn: Callable[[NorthTrackerGpsDevice], bool] | None = None

# Unified sensor descriptions for both main GPS devices and Bluetooth sensors
SENSOR_DESCRIPTIONS: tuple[NorthTrackerSensorEntityDescription, ...] = (
    # GPS device sensors
    NorthTrackerSensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.last_seen,
        exists_fn=lambda device: hasattr(device, 'last_seen') and device.last_seen is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        icon= "mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery_voltage,
        exists_fn=lambda device: hasattr(device, 'battery_voltage') and device.battery_voltage is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:counter",
        value_fn=lambda device: device.odometer,
        exists_fn=lambda device: hasattr(device, 'odometer') and device.odometer is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="gps_signal",
        translation_key="gps_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.gps_signal,
        exists_fn=lambda device: hasattr(device, 'gps_signal') and device.gps_signal is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="network_signal",
        translation_key="network_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.network_signal,
        exists_fn=lambda device: hasattr(device, 'network_signal') and device.network_signal is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="speed",
        translation_key="speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        suggested_display_precision=0,
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.speed,
        exists_fn=lambda device: hasattr(device, 'speed') and device.speed is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="report_frequency",
        translation_key="report_frequency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter",
        value_fn=lambda device: device.report_frequency,
        exists_fn=lambda device: hasattr(device, 'report_frequency') and device.report_frequency is not None,
    ),
    # Bluetooth sensor sensors
    NorthTrackerSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        icon="mdi:thermometer",
        value_fn=lambda device: device.temperature,
        exists_fn=lambda device: hasattr(device, 'temperature') and device.temperature is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        suggested_display_precision=0,
        icon="mdi:water-percent",
        value_fn=lambda device: device.humidity,
        exists_fn=lambda device: hasattr(device, 'humidity') and device.humidity is not None,
    ),
    NorthTrackerSensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda device: hasattr(device, 'battery_percentage') and device.battery_percentage is not None,
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the sensor platform and discover new entities."""
    from .base import BasePlatformSetup
    
    def create_sensor_entity(coordinator, device_id, description):
        """Create a sensor entity instance.""" 
        return NorthTrackerSensor(coordinator, device_id, description)
    
    # Use the generic platform setup helper
    platform_setup = BasePlatformSetup(
        platform_name="sensor",
        entity_class=NorthTrackerSensor,
        entity_descriptions=SENSOR_DESCRIPTIONS,
        create_entity_callback=create_sensor_entity
    )
    
    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerSensor(NorthTrackerEntity, SensorEntity):
    """Defines a North-Tracker sensor for both GPS and Bluetooth devices."""

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int, description: NorthTrackerSensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = validate_entity_id(f"{device_id}_{description.key}")

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
            
        # Use value_fn from entity description
        if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
            value = self.entity_description.value_fn(device)
        else:
            # This should not happen with our current setup, but keeping as fallback
            value = getattr(device, self.entity_description.key, None)
        
        LOGGER.debug("Sensor %s for device %s has raw value: %s", self.entity_description.key, device.name, value)
        
        # Validate the value based on the sensor type
        if value is None:
            LOGGER.debug("Sensor %s for device %s has None value", self.entity_description.key, device.name)
            return None
            
        # Additional validation for specific sensor types
        if self.entity_description.key == "battery_voltage" and isinstance(value, (int, float)):
            # Battery voltage should be reasonable (0-50V for most vehicles)
            if not (0 <= value <= MAX_BATTERY_VOLTAGE_READING):
                LOGGER.warning("Battery voltage out of range for device %s: %s", device.name, value)
                return None
        elif self.entity_description.key in ["gps_signal", "network_signal"] and isinstance(value, (int, float)):
            # Signal strength should be 0-100 percent
            if not (MIN_SIGNAL_STRENGTH <= value <= MAX_SIGNAL_STRENGTH):
                LOGGER.warning("Signal strength out of range for device %s (%s): %s", device.name, self.entity_description.key, value)
                return None
        elif self.entity_description.key == "network_signal" and hasattr(device, 'has_position') and not device.has_position:
            # Network signal should only be available when device has GPS data
            LOGGER.debug("Network signal unavailable for device %s - no GPS position data", device.name)
            return None
        
        LOGGER.debug("Sensor %s for device %s returning validated value: %s", self.entity_description.key, device.name, value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes or {}
        
        # Add sensor-specific attributes
        if hasattr(self, 'entity_description'):
            attributes["sensor_type"] = self.entity_description.key
            
            # Add signal quality text for signal sensors
            if self.entity_description.key in ["gps_signal", "network_signal"]:
                current_value = self.native_value
                if isinstance(current_value, (int, float)):
                    attributes["signal_quality"] = get_signal_quality_text(int(current_value))
        
        return attributes if attributes else None
