"""GPS Device class for North-Tracker GPS trackers."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING

from .base import NorthTrackerBaseDevice, DeviceCapabilities
from ..const import (
    LOGGER,
    MAX_BLUETOOTH_SENSORS_PER_DEVICE,
    SIGNAL_SCALE_MIN,
    SIGNAL_SCALE_MAX,
    MAX_SIGNAL_STRENGTH,
    GPS_COORDINATE_PRECISION,
)
from ..helpers import parse_northtracker_timestamp, round_gps_coordinate

if TYPE_CHECKING:
    from ..api import NorthTracker


# Define GPS device capabilities once
GPS_DEVICE_CAPABILITIES = DeviceCapabilities(
    # Tracker capabilities
    has_location=True,
    has_speed=True,
    has_course=True,
    
    # Sensor capabilities
    has_battery_voltage=True,
    has_gps_signal=True,
    has_network_signal=True,
    has_odometer=True,
    has_report_frequency=True,
    has_last_seen=True,
    
    # Binary sensor capabilities
    has_bluetooth_enabled=True,
    
    # Switch capabilities
    has_alarm=True,
    has_low_battery_alert=True,
    has_geofence=True,
    has_digital_outputs=True,
    has_digital_inputs=True,
    
    # Number capabilities
    has_low_battery_threshold=True,
    
    # Button capabilities
    has_refresh=True,
    
    # Supported entity keys
    supported_sensors=[
        "last_seen",
        "battery_voltage", 
        "odometer",
        "gps_signal",
        "network_signal",
        "speed",
        "report_frequency",
    ],
    supported_binary_sensors=[
        "bluetooth_enabled",
    ],
    supported_switches=[
        "alarm_status",
        "low_battery_alert_enabled",
        "geofence",
    ],
    supported_numbers=[
        "low_battery_threshold",
    ],
)


class NorthTrackerGpsDevice(NorthTrackerBaseDevice):
    """Represents a North-Tracker GPS device with all its data and capabilities."""
    
    def __init__(self, tracker: "NorthTracker", device_data: dict[str, Any]) -> None:
        """Initialize a GPS device instance."""
        super().__init__(tracker)
        self._device_data = device_data
        self._device_data_extra: dict[str, Any] = {}
        self._device_lock_data: dict[str, Any] = {}
        self._device_gps_data: dict[str, Any] = {}
        self._device_features_data: dict[str, Any] = {}
        
        LOGGER.debug("Initializing GPS device: %s (ID: %s)", self.name, self.id)
        
        # Dynamically discover digital inputs and outputs
        self._available_inputs = self._discover_digital_inputs()
        self._available_outputs = self._discover_digital_outputs()
        
        # Dynamically discover Bluetooth sensors
        self._available_bluetooth_sensors = self._discover_bluetooth_sensors()
        
        LOGGER.debug(
            "Device %s discovered capabilities: %d inputs, %d outputs, %d bluetooth sensors", 
            self.name, len(self._available_inputs), len(self._available_outputs),
            len(self._available_bluetooth_sensors)
        )

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the GPS device capabilities."""
        return GPS_DEVICE_CAPABILITIES

    async def async_update(self) -> bool:
        """Update device with latest information from the API.
        
        Returns True if device data has actually changed, False otherwise.
        """
        LOGGER.debug("Updating device %s (ID: %s)", self.name, self.id)
        data_changed = False
        
        try:
            # Get detailed device information
            resp_details = await self.tracker.get_unit_details(self.id, self.device_type)
            if resp_details.success:
                if self._device_data_extra != resp_details.data:
                    LOGGER.debug("Device details changed for %s", self.name)
                    self._device_data_extra = resp_details.data
                    data_changed = True

            # Get lock status
            resp_lock = await self.tracker.get_unit_lock_status(self.id)
            if resp_lock.success:
                if self._device_lock_data != resp_lock.data:
                    LOGGER.debug("Lock status changed for %s", self.name)
                    self._device_lock_data = resp_lock.data
                    data_changed = True

            # Get unit features (for battery alert settings etc.)
            resp_features = await self.tracker.get_unit_features(self.imei)
            if resp_features.success:
                features_data = resp_features.data
                if features_data and len(features_data) > 0:
                    if self._device_features_data != features_data[0]:
                        LOGGER.debug("Unit features changed for %s", self.name)
                        self._device_features_data = features_data[0]
                        data_changed = True
                
            self._last_update = datetime.now()
            return data_changed
            
        except Exception as err:
            LOGGER.error("Error updating device %s: %s", self.name, err)
            raise

    def update_gps_data(self, gps_data: dict[str, Any]) -> bool:
        """Update the device with real-time location data.
        
        Returns True if the GPS data has actually changed, False otherwise.
        """
        if self._device_gps_data == gps_data:
            LOGGER.debug("GPS data unchanged for device %s", self.name)
            return False
            
        LOGGER.debug(
            "GPS data changed for device %s: has_position=%s, lat=%s, lon=%s", 
            self.name, gps_data.get("HasPosition"), 
            gps_data.get("Latitude"), gps_data.get("Longitude")
        )
        self._device_gps_data = gps_data
        
        # Re-discover Bluetooth sensors when GPS data changes
        self._available_bluetooth_sensors = self._discover_bluetooth_sensors()
        
        return True

    # -------------------------------------------------------------------------
    # Discovery methods
    # -------------------------------------------------------------------------
    
    def _discover_digital_inputs(self) -> list[int]:
        """Discover available digital inputs based on device data."""
        inputs = []
        for key, value in self._device_data.items():
            if key.startswith("Din") and key.endswith("Status"):
                try:
                    input_num = int(key[3:-6])
                    inputs.append(input_num)
                    LOGGER.debug("Found digital input %d for device %s", input_num, self.name)
                except ValueError:
                    pass
        return sorted(inputs)
    
    def _discover_digital_outputs(self) -> list[int]:
        """Discover available digital outputs based on device data."""
        outputs = []
        for key, value in self._device_data.items():
            if key.startswith("Dout") and key.endswith("Status"):
                try:
                    output_num = int(key[4:-6])
                    outputs.append(output_num)
                    LOGGER.debug("Found digital output %d for device %s", output_num, self.name)
                except ValueError:
                    pass
        return sorted(outputs)

    def _discover_bluetooth_sensors(self) -> list[dict[str, Any]]:
        """Discover available Bluetooth sensors based on GPS data."""
        sensors = []
        paired_sensors = self._device_gps_data.get("PairedSensors", [])
        
        for sensor in paired_sensors:
            if isinstance(sensor, dict):
                serial_number = sensor.get("SerialNumber")
                paired_slot = sensor.get("PairedSlot")
                bluetooth_info = sensor.get("bluetooth_info", {})
                latest_data = sensor.get("latest_sensor_data", {})
                
                if serial_number and paired_slot and bluetooth_info:
                    slot_number = int(paired_slot)
                    if slot_number > MAX_BLUETOOTH_SENSORS_PER_DEVICE:
                        LOGGER.warning(
                            "Bluetooth sensor %s in slot %d exceeds max slots (%d) - skipping", 
                            serial_number, slot_number, MAX_BLUETOOTH_SENSORS_PER_DEVICE
                        )
                        continue
                    
                    sensor_config = {
                        "serial_number": serial_number,
                        "paired_slot": slot_number,
                        "name": bluetooth_info.get("Name", f"Bluetooth Sensor {serial_number}"),
                        "enable_temperature": bool(bluetooth_info.get("EnableTemperature", 0)),
                        "enable_humidity": bool(bluetooth_info.get("EnableHumidity", 0)),
                        "enable_door_sensor": bool(bluetooth_info.get("EnableDoorSensor", 0)),
                        "has_data": bool(latest_data),
                        "latest_sensor_data": latest_data
                    }
                    sensors.append(sensor_config)
                    LOGGER.debug(
                        "Found Bluetooth sensor %s (%s) for device %s", 
                        serial_number, sensor_config["name"], self.name
                    )
        
        if len(sensors) > MAX_BLUETOOTH_SENSORS_PER_DEVICE:
            LOGGER.warning(
                "Device %s has %d Bluetooth sensors, limiting to %d", 
                self.name, len(sensors), MAX_BLUETOOTH_SENSORS_PER_DEVICE
            )
            sensors = sensors[:MAX_BLUETOOTH_SENSORS_PER_DEVICE]
        
        return sensors

    # -------------------------------------------------------------------------
    # Required abstract properties
    # -------------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return bool(self._device_data.get("ID") and self._device_data.get("NameOnly"))

    @property
    def available_inputs(self) -> list[int]:
        """Return list of available digital input numbers."""
        return self._available_inputs

    @property
    def available_outputs(self) -> list[int]:
        """Return list of available digital output numbers."""
        return self._available_outputs

    @property
    def available_bluetooth_sensors(self) -> list[dict[str, Any]]:
        """Return list of available Bluetooth sensors."""
        return self._available_bluetooth_sensors

    @property
    def id(self) -> int:
        """Return the device ID."""
        device_id = self._device_data.get("ID", 0)
        return int(device_id) if device_id is not None else 0
    
    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device_data.get("NameOnly", "Unknown Device")

    @property
    def imei(self) -> str:
        """Return the device IMEI."""
        return self._device_data.get("Imei", "")

    @property
    def device_type(self) -> str:
        """Return the device type."""
        return self._device_data.get("DeviceType", "gps")

    @property
    def model(self) -> str:
        """Return the device model."""
        return self._device_data.get("GpsModel", "")

    # -------------------------------------------------------------------------
    # GPS/Location properties
    # -------------------------------------------------------------------------

    @property
    def latitude(self) -> float | None:
        """Return current latitude with configured precision."""
        lat = self._device_gps_data.get("Latitude")
        if lat is None:
            return None
        try:
            return round_gps_coordinate(float(lat))
        except (ValueError, TypeError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return current longitude with configured precision."""
        lon = self._device_gps_data.get("Longitude")
        if lon is None:
            return None
        try:
            return round_gps_coordinate(float(lon))
        except (ValueError, TypeError):
            return None

    @property
    def has_position(self) -> bool:
        """Return True if device has GPS position data."""
        return bool(self._device_gps_data.get("HasPosition", False))

    @property
    def gps_accuracy(self) -> int:
        """Return GPS accuracy level (0-5)."""
        accuracy = self._device_gps_data.get("GPSAccuracy", 0)
        try:
            return int(accuracy)
        except (ValueError, TypeError):
            return 0

    @property
    def speed(self) -> int:
        """Return current speed in km/h."""
        speed = self._device_gps_data.get("Speed", 0)
        try:
            return int(speed)
        except (ValueError, TypeError):
            return 0
    
    @property
    def course(self) -> int:
        """Return course/heading of the device in degrees."""
        course = self._device_gps_data.get("Azimuth", 0)
        try:
            course_int = int(float(course))
            if 0 <= course_int <= 359:
                return course_int
            return 0
        except (ValueError, TypeError):
            return 0

    # -------------------------------------------------------------------------
    # Sensor properties
    # -------------------------------------------------------------------------

    @property
    def gps_signal(self) -> int | None:
        """Return GPS signal strength as percentage (0-100%)."""
        accuracy = self._device_gps_data.get("GPSAccuracy")
        if accuracy is None:
            return None
        try:
            accuracy_int = int(accuracy)
            if accuracy_int < SIGNAL_SCALE_MIN:
                return 0
            elif accuracy_int > SIGNAL_SCALE_MAX:
                return MAX_SIGNAL_STRENGTH
            else:
                return int((accuracy_int / SIGNAL_SCALE_MAX) * MAX_SIGNAL_STRENGTH)
        except (ValueError, TypeError):
            return None

    @property
    def network_signal(self) -> int | None:
        """Return network signal strength as percentage (0-100%)."""
        signal = self._device_gps_data.get("NetworkQuality")
        if signal is None:
            return None
        try:
            signal_int = int(signal)
            if signal_int < SIGNAL_SCALE_MIN:
                return 0
            elif signal_int > SIGNAL_SCALE_MAX:
                return MAX_SIGNAL_STRENGTH
            else:
                return int((signal_int / SIGNAL_SCALE_MAX) * MAX_SIGNAL_STRENGTH)
        except (ValueError, TypeError):
            return None

    @property
    def last_seen(self) -> datetime | None:
        """Return the last seen timestamp."""
        last_seen_str = self._device_gps_data.get("Send_Time")
        return parse_northtracker_timestamp(last_seen_str)

    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage."""
        battery_str = self._device_data.get("BatteryVoltage")
        if battery_str is None:
            return None
        try:
            if isinstance(battery_str, (int, float)):
                return float(battery_str) / 1000.0
            elif isinstance(battery_str, str):
                clean_str = ''.join(c for c in battery_str if c.isdigit() or c == '.')
                if clean_str:
                    return float(clean_str) / 1000.0
            return None
        except (ValueError, TypeError):
            return None

    @property
    def odometer(self) -> float | None:
        """Return odometer reading in kilometers."""
        odometer = self._device_data.get("Odometer")
        if odometer is None:
            return None
        try:
            return float(odometer)
        except (ValueError, TypeError):
            return None

    @property
    def report_frequency(self) -> int | None:
        """Return report frequency in seconds."""
        frequency = self._device_gps_data.get("ReportFrequency")
        if frequency is None:
            return None
        try:
            return int(frequency)
        except (ValueError, TypeError):
            return None

    @property
    def bluetooth_enabled(self) -> bool:
        """Return True if Bluetooth is enabled on the device."""
        bluetooth_enabled = self._device_data_extra.get("terminal", {}).get("BluetoothStatus", False)
        return bool(bluetooth_enabled)

    # -------------------------------------------------------------------------
    # Switch/Control properties
    # -------------------------------------------------------------------------

    @property
    def alarm_status(self) -> bool | None:
        """Return alarm status."""
        return self._device_data.get("AlarmStatus")

    @property
    def low_battery_alert_enabled(self) -> bool:
        """Return whether low battery alert is enabled."""
        return self._device_features_data.get("LowBatteryAlertEnabled", False)
    
    @property
    def low_battery_threshold(self) -> float | None:
        """Return low battery alert threshold in volts."""
        threshold = self._device_features_data.get("LowBatteryThreshold")
        if threshold is None:
            return None
        try:
            return float(threshold)
        except (ValueError, TypeError):
            return None

    @property
    def lock_status(self) -> bool:
        """Return whether the device is locked."""
        return bool(self._device_lock_data.get("lockedstatus", False))

    @property
    def locked_by(self) -> str:
        """Return who locked the device."""
        return self._device_lock_data.get("lockedBy", "")

    # -------------------------------------------------------------------------
    # Digital I/O methods
    # -------------------------------------------------------------------------

    def get_digital_input_state(self, input_number: int) -> bool | None:
        """Get the state of a digital input."""
        key = f"Din{input_number}Status"
        status = self._device_data.get(key)
        if status is None:
            return None
        return status.lower() == "on" if isinstance(status, str) else bool(status)

    def get_digital_output_state(self, output_number: int) -> bool | None:
        """Get the state of a digital output.""" 
        key = f"Dout{output_number}Status"
        status = self._device_data.get(key)
        if status is None:
            return None
        return status.lower() == "on" if isinstance(status, str) else bool(status)

    def get_output_status(self, output_number: int) -> bool:
        """Get the status of a digital output (used by switch entities)."""
        state = self.get_digital_output_state(output_number)
        return state if state is not None else False

    def get_input_status(self, input_number: int) -> bool:
        """Get the status of a digital input (used by switch entities)."""
        state = self.get_digital_input_state(input_number)
        return state if state is not None else False

    # -------------------------------------------------------------------------
    # Info properties
    # -------------------------------------------------------------------------

    @property
    def registration_number(self) -> str | None:
        """Return the vehicle registration number."""
        return self._device_data.get("RegNr")

    @property
    def subscription_type(self) -> str:
        """Return the device subscription type."""
        return self._device_data.get("SubscriptionType", "")

    @property
    def operating_time(self) -> str:
        """Return the device operating time."""
        return self._device_data.get("OperatingTime", "")

    @property
    def sos_alarm_enabled(self) -> bool:
        """Return whether SOS alarm is enabled."""
        return bool(self._device_data_extra.get("SoSAlarmEnabled", False))
