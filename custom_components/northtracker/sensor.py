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

from .const import DOMAIN, MIN_SIGNAL_STRENGTH, MAX_SIGNAL_STRENGTH, MAX_BATTERY_VOLTAGE_READING
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .devices import NorthTrackerBaseDevice
from .helpers import get_signal_quality_text
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerSensorEntityDescription(SensorEntityDescription):
    """Describes a North-Tracker sensor entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerBaseDevice], Any] | None = None


# Unified sensor descriptions for both main GPS devices and Bluetooth sensors
SENSOR_DESCRIPTIONS: tuple[NorthTrackerSensorEntityDescription, ...] = (
    # GPS device sensors
    NorthTrackerSensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.last_seen,
    ),
    NorthTrackerSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_voltage,
    ),
    NorthTrackerSensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        value_fn=lambda device: device.odometer,
    ),
    NorthTrackerSensorEntityDescription(
        key="gps_signal",
        translation_key="gps_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.gps_signal,
    ),
    NorthTrackerSensorEntityDescription(
        key="network_signal",
        translation_key="network_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.network_signal,
    ),
    NorthTrackerSensorEntityDescription(
        key="speed",
        translation_key="speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.speed,
    ),
    NorthTrackerSensorEntityDescription(
        key="report_frequency",
        translation_key="report_frequency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.report_frequency,
    ),
    # Bluetooth sensor sensors
    NorthTrackerSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        value_fn=lambda device: device.temperature,
    ),
    NorthTrackerSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        suggested_display_precision=0,
        value_fn=lambda device: device.humidity,
    ),
    NorthTrackerSensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_percentage,
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
            return None
            
        device = self.device
        if device is None:
            return None
            
        # Use value_fn from entity description
        if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
            value = self.entity_description.value_fn(device)
        else:
            value = getattr(device, self.entity_description.key, None)
        
        if value is None:
            return None
            
        # Additional validation for specific sensor types
        if self.entity_description.key == "battery_voltage" and isinstance(value, (int, float)):
            if not (0 <= value <= MAX_BATTERY_VOLTAGE_READING):
                return None
        elif self.entity_description.key in ["gps_signal", "network_signal"] and isinstance(value, (int, float)):
            if not (MIN_SIGNAL_STRENGTH <= value <= MAX_SIGNAL_STRENGTH):
                return None
        elif self.entity_description.key == "network_signal" and hasattr(device, 'has_position') and not device.has_position:
            return None
        
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes or {}
        
        # Add signal quality text for signal sensors
        if hasattr(self, 'entity_description'):
            if self.entity_description.key in ["gps_signal", "network_signal"]:
                current_value = self.native_value
                if isinstance(current_value, (int, float)):
                    attributes["signal_quality"] = get_signal_quality_text(int(current_value))
        
        return attributes if attributes else None
