"""Bluetooth Sensor Device class for North-Tracker Bluetooth sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from .base import NorthTrackerBaseDevice, DeviceCapabilities
from ..const import LOGGER
from ..helpers import (
    parse_northtracker_timestamp,
    safe_int,
    safe_float,
    generate_stable_id,
)

if TYPE_CHECKING:
    from .gps_device import NorthTrackerGpsDevice


# Define Bluetooth sensor capabilities once
BLUETOOTH_SENSOR_CAPABILITIES = DeviceCapabilities(
    # Sensor capabilities
    has_temperature=True,
    has_humidity=True,
    has_battery_percentage=True,
    has_battery_voltage=True,
    has_last_seen=True,
    # Binary sensor capabilities
    has_door_sensor=True,
    # Supported entity keys
    supported_sensors=[
        "temperature",
        "humidity",
        "battery_percentage",
        "battery_voltage",
        "last_seen",
    ],
    supported_binary_sensors=[
        "door_sensor",
    ],
    supported_switches=[],
    supported_numbers=[],
)


class NorthTrackerSensorDevice(NorthTrackerBaseDevice):
    """Represents a virtual Bluetooth sensor device connected to a main GPS tracker."""

    def __init__(
        self, parent_device: "NorthTrackerGpsDevice", bt_sensor_data: dict[str, Any]
    ) -> None:
        """Initialize a Bluetooth sensor device instance."""
        super().__init__(parent_device.tracker)
        self.parent_device = parent_device
        self._bt_sensor_data = bt_sensor_data
        self._serial_number = bt_sensor_data["serial_number"]
        self._paired_slot = bt_sensor_data["paired_slot"]
        self._sensor_name = bt_sensor_data["name"]

        LOGGER.debug(
            "Created Bluetooth device for sensor: %s (%s, PairedSlot %d, Device ID %d)",
            self._sensor_name,
            self._serial_number,
            self._paired_slot,
            self.id,
        )

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the Bluetooth sensor capabilities."""
        return BLUETOOTH_SENSOR_CAPABILITIES

    # -------------------------------------------------------------------------
    # Required abstract properties
    # -------------------------------------------------------------------------

    @property
    def id(self) -> int:
        """Return a unique device ID based on serial number.

        Uses a hash of the serial number to generate a stable, unique ID
        that won't collide with GPS device IDs.
        """
        return generate_stable_id(self._serial_number)

    @property
    def name(self) -> str:
        """Return the Bluetooth sensor name."""
        return self._sensor_name

    @property
    def device_type(self) -> str:
        """Return the device type."""
        return "bluetooth_sensor"

    @property
    def model(self) -> str:
        """Return the device model."""
        return "Sensor"

    @property
    def imei(self) -> str:
        """Return the device IMEI (same as serial number for Bluetooth sensors)."""
        return self._serial_number

    @property
    def available(self) -> bool:
        """Return True if Bluetooth sensor has data."""
        return self._bt_sensor_data.get("has_data", False)

    @property
    def sensor_data(self) -> dict[str, Any]:
        """Return the Bluetooth sensor data."""
        return self._bt_sensor_data

    async def async_update(self) -> bool:
        """Update is handled by parent device. Always return False (no direct changes)."""
        return False

    # -------------------------------------------------------------------------
    # Helper to get current sensor data from parent
    # -------------------------------------------------------------------------

    def _get_sensor_data(self) -> dict[str, Any] | None:
        """Get the current sensor data for this Bluetooth sensor from parent."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                return sensor.get("latest_sensor_data", {})
        return None

    # -------------------------------------------------------------------------
    # Sensor properties
    # -------------------------------------------------------------------------

    @property
    def temperature(self) -> float | None:
        """Return temperature reading from this Bluetooth sensor."""
        sensor_data = self._get_sensor_data()
        if sensor_data is None:
            return None
        return safe_float(sensor_data.get("Temperature"))

    @property
    def humidity(self) -> int | None:
        """Return humidity reading from this Bluetooth sensor."""
        sensor_data = self._get_sensor_data()
        if sensor_data is None:
            return None
        return safe_int(sensor_data.get("Humidity"))

    @property
    def battery_percentage(self) -> int | None:
        """Return battery percentage from this Bluetooth sensor."""
        sensor_data = self._get_sensor_data()
        if sensor_data is None:
            return None
        return safe_int(sensor_data.get("BatteryPercentage"))

    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage from this Bluetooth sensor."""
        sensor_data = self._get_sensor_data()
        if sensor_data is None:
            return None
        voltage = safe_float(sensor_data.get("BatteryVoltage"))
        # Convert from millivolts to volts
        return voltage / 1000.0 if voltage is not None else None

    @property
    def magnetic_contact(self) -> bool | None:
        """Return magnetic contact state from this Bluetooth sensor."""
        sensor_data = self._get_sensor_data()
        if sensor_data is None:
            return None
        magnetic_state = sensor_data.get("MagneticField")
        if magnetic_state is None:
            return None
        return bool(magnetic_state)

    @property
    def last_seen(self) -> datetime | None:
        """Return last seen timestamp for this Bluetooth sensor."""
        sensor_data = self._get_sensor_data()
        if sensor_data is None:
            return None
        send_time_str = sensor_data.get("Send_Time")
        return parse_northtracker_timestamp(send_time_str)
