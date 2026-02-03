"""Base device class for North-Tracker devices."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..api import NorthTracker


@dataclass
class DeviceCapabilities:
    """Defines what capabilities/features a device type supports.
    
    This is used to determine which entities should be created for each device type,
    eliminating the need for complex if-statements in platform setup.
    """
    # Tracker capabilities
    has_location: bool = False
    has_speed: bool = False
    has_course: bool = False
    
    # Sensor capabilities
    has_temperature: bool = False
    has_humidity: bool = False
    has_battery_percentage: bool = False
    has_battery_voltage: bool = False
    has_gps_signal: bool = False
    has_network_signal: bool = False
    has_odometer: bool = False
    has_report_frequency: bool = False
    has_last_seen: bool = False
    
    # Binary sensor capabilities
    has_bluetooth_enabled: bool = False
    has_door_sensor: bool = False
    
    # Switch capabilities
    has_alarm: bool = False
    has_low_battery_alert: bool = False
    has_geofence: bool = False
    has_digital_outputs: bool = False
    has_digital_inputs: bool = False
    
    # Number capabilities
    has_low_battery_threshold: bool = False
    
    # Button capabilities
    has_refresh: bool = False
    
    # Sensor keys that this device type supports (for dynamic entity creation)
    supported_sensors: list[str] = field(default_factory=list)
    supported_binary_sensors: list[str] = field(default_factory=list)
    supported_switches: list[str] = field(default_factory=list)
    supported_numbers: list[str] = field(default_factory=list)


class NorthTrackerBaseDevice(ABC):
    """Abstract base class for all North-Tracker devices.
    
    Provides common interface and properties that all device types must implement.
    """
    
    def __init__(self, tracker: "NorthTracker") -> None:
        """Initialize the base device."""
        self.tracker = tracker
        self._last_update: datetime | None = None
    
    @property
    @abstractmethod
    def id(self) -> int:
        """Return the unique device ID."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the device name."""
        ...
    
    @property
    @abstractmethod
    def device_type(self) -> str:
        """Return the device type identifier."""
        ...
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Return the device model."""
        ...
    
    @property
    @abstractmethod
    def imei(self) -> str:
        """Return the device IMEI or serial number."""
        ...
    
    @property
    @abstractmethod
    def available(self) -> bool:
        """Return True if the device is available."""
        ...
    
    @property
    @abstractmethod
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""
        ...
    
    @abstractmethod
    async def async_update(self) -> bool:
        """Update device data from API. Returns True if data changed."""
        ...
    
    def supports_sensor(self, sensor_key: str) -> bool:
        """Check if device supports a specific sensor."""
        return sensor_key in self.capabilities.supported_sensors
    
    def supports_binary_sensor(self, sensor_key: str) -> bool:
        """Check if device supports a specific binary sensor."""
        return sensor_key in self.capabilities.supported_binary_sensors
    
    def supports_switch(self, switch_key: str) -> bool:
        """Check if device supports a specific switch."""
        return switch_key in self.capabilities.supported_switches
    
    def supports_number(self, number_key: str) -> bool:
        """Check if device supports a specific number entity."""
        return number_key in self.capabilities.supported_numbers
    
    # Common optional properties with default implementations
    @property
    def last_seen(self) -> datetime | None:
        """Return the last seen timestamp. Override in subclass if supported."""
        return None
    
    @property
    def temperature(self) -> float | None:
        """Return temperature. Override in subclass if supported."""
        return None
    
    @property
    def humidity(self) -> int | None:
        """Return humidity. Override in subclass if supported."""
        return None
    
    @property
    def battery_percentage(self) -> int | None:
        """Return battery percentage. Override in subclass if supported."""
        return None
    
    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage. Override in subclass if supported."""
        return None
