"""GPS Device class for NorthTracker GPS trackers."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..const import (
    LOGGER,
    MAX_BLUETOOTH_SENSORS_PER_DEVICE,
    MAX_SIGNAL_STRENGTH,
    SIGNAL_SCALE_MAX,
    SIGNAL_SCALE_MIN,
)
from ..helpers import (
    parse_northtracker_timestamp,
    round_gps_coordinate,
    safe_float,
    safe_int,
)
from .base import DeviceCapabilities, NorthTrackerBaseDevice

if TYPE_CHECKING:
    from ..api import NorthTracker

# The API spells I/O numbers out in its label keys ("DINTwoBtnLabel")
_ORDINAL_WORDS = (
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
)


def _ordinal_word(number: int) -> str:
    """Return the spelled-out form of an I/O number as the API writes it."""
    if 1 <= number <= len(_ORDINAL_WORDS):
        return _ORDINAL_WORDS[number - 1]
    return str(number)


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
    has_low_battery_threshold=True,
    # Binary sensor capabilities
    has_bluetooth_enabled=True,
    has_low_battery_alert=True,
    has_geofence=True,
    has_digital_outputs=True,
    has_digital_inputs=True,
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
        "low_battery_threshold",
    ],
    supported_binary_sensors=[
        "bluetooth_enabled",
        "low_battery_alert_enabled",
        "geofence_enabled",
    ],
)


class NorthTrackerGpsDevice(NorthTrackerBaseDevice):
    """Represents a NorthTracker GPS device with all its data and capabilities."""

    def __init__(self, tracker: NorthTracker, device_data: dict[str, Any]) -> None:
        """Initialize a GPS device instance."""
        super().__init__(tracker)
        self._device_data = device_data
        self._device_data_extra: dict[str, Any] = {}
        self._device_lock_data: dict[str, Any] = {}
        self._device_gps_data: dict[str, Any] = {}
        self._device_features_data: dict[str, Any] = {}
        # Aggregated geofence state, refreshed by the coordinator each update.
        # True = all geofences enabled, False = at least one disabled, None = none exist.
        self._geofence_enabled: bool | None = None

        LOGGER.debug("Initializing GPS device: %s (ID: %s)", self.name, self.id)

        # Dynamically discover digital inputs and outputs
        self._available_inputs = self._discover_digital_inputs()
        self._available_outputs = self._discover_digital_outputs()

        # Dynamically discover Bluetooth sensors
        self._available_bluetooth_sensors = self._discover_bluetooth_sensors()

        LOGGER.debug(
            "Device %s discovered capabilities: %d inputs, %d outputs, %d bluetooth sensors",
            self.name,
            len(self._available_inputs),
            len(self._available_outputs),
            len(self._available_bluetooth_sensors),
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
            resp_details = await self.tracker.get_unit_details(
                self.id, self.device_type
            )
            if resp_details.success and self._device_data_extra != resp_details.data:
                LOGGER.debug("Device details changed for %s", self.name)
                self._device_data_extra = resp_details.data
                data_changed = True

            # Get lock status
            resp_lock = await self.tracker.get_unit_lock_status(self.id)
            if resp_lock.success and self._device_lock_data != resp_lock.data:
                LOGGER.debug("Lock status changed for %s", self.name)
                self._device_lock_data = resp_lock.data
                data_changed = True

            # Get unit features (for battery alert settings etc.)
            resp_features = await self.tracker.get_unit_features(self.imei)
            if resp_features.success:
                features_data = resp_features.data
                if features_data and self._device_features_data != features_data[0]:
                    LOGGER.debug("Unit features changed for %s", self.name)
                    self._device_features_data = features_data[0]
                    data_changed = True

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
            self.name,
            gps_data.get("HasPosition"),
            gps_data.get("Latitude"),
            gps_data.get("Longitude"),
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
        for key in self._device_data:
            if key.startswith("Din") and key.endswith("Status"):
                try:
                    input_num = int(key[3:-6])
                    inputs.append(input_num)
                    LOGGER.debug(
                        "Found digital input %d for device %s", input_num, self.name
                    )
                except ValueError:
                    pass
        return sorted(inputs)

    def _discover_digital_outputs(self) -> list[int]:
        """Discover available digital outputs based on device data."""
        outputs = []
        for key in self._device_data:
            if key.startswith("Dout") and key.endswith("Status"):
                try:
                    output_num = int(key[4:-6])
                    outputs.append(output_num)
                    LOGGER.debug(
                        "Found digital output %d for device %s", output_num, self.name
                    )
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
                            serial_number,
                            slot_number,
                            MAX_BLUETOOTH_SENSORS_PER_DEVICE,
                        )
                        continue

                    sensor_config = {
                        "serial_number": serial_number,
                        "paired_slot": slot_number,
                        "name": bluetooth_info.get(
                            "Name", f"Bluetooth Sensor {serial_number}"
                        ),
                        "enable_temperature": bool(
                            bluetooth_info.get("EnableTemperature", 0)
                        ),
                        "enable_humidity": bool(
                            bluetooth_info.get("EnableHumidity", 0)
                        ),
                        "enable_door_sensor": bool(
                            bluetooth_info.get("EnableDoorSensor", 0)
                        ),
                        "has_data": bool(latest_data),
                        "latest_sensor_data": latest_data,
                    }
                    sensors.append(sensor_config)
                    LOGGER.debug(
                        "Found Bluetooth sensor %s (%s) for device %s",
                        serial_number,
                        sensor_config["name"],
                        self.name,
                    )

        if len(sensors) > MAX_BLUETOOTH_SENSORS_PER_DEVICE:
            LOGGER.warning(
                "Device %s has %d Bluetooth sensors, limiting to %d",
                self.name,
                len(sensors),
                MAX_BLUETOOTH_SENSORS_PER_DEVICE,
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

    def _get_coordinate(self, key: str) -> float | None:
        """Get a GPS coordinate value with precision handling."""
        value = self._device_gps_data.get(key)
        if value is None:
            return None
        try:
            return round_gps_coordinate(float(value))
        except (ValueError, TypeError):
            return None

    @property
    def latitude(self) -> float | None:
        """Return current latitude with configured precision."""
        return self._get_coordinate("Latitude")

    @property
    def longitude(self) -> float | None:
        """Return current longitude with configured precision."""
        return self._get_coordinate("Longitude")

    @property
    def has_position(self) -> bool:
        """Return True if device has GPS position data."""
        return bool(self._device_gps_data.get("HasPosition", False))

    @property
    def gps_accuracy(self) -> int:
        """Return GPS accuracy level (0-5)."""
        return safe_int(self._device_gps_data.get("GPSAccuracy"), 0)

    @property
    def speed(self) -> int:
        """Return current speed in km/h."""
        return safe_int(self._device_gps_data.get("Speed"), 0)

    @property
    def course(self) -> int:
        """Return course/heading of the device in degrees."""
        course = safe_int(self._device_gps_data.get("Azimuth"), 0)
        return course if 0 <= course <= 359 else 0

    # -------------------------------------------------------------------------
    # Sensor properties
    # -------------------------------------------------------------------------

    def _calculate_signal_percentage(self, value: Any) -> int | None:
        """Calculate signal strength as percentage (0-100%) from raw value."""
        if value is None:
            return None
        try:
            value_int = int(value)
            if value_int < SIGNAL_SCALE_MIN:
                return 0
            if value_int > SIGNAL_SCALE_MAX:
                return MAX_SIGNAL_STRENGTH
            return int((value_int / SIGNAL_SCALE_MAX) * MAX_SIGNAL_STRENGTH)
        except (ValueError, TypeError):
            return None

    @property
    def gps_signal(self) -> int | None:
        """Return GPS signal strength as percentage (0-100%)."""
        return self._calculate_signal_percentage(
            self._device_gps_data.get("GPSAccuracy")
        )

    @property
    def network_signal(self) -> int | None:
        """Return network signal strength as percentage (0-100%)."""
        return self._calculate_signal_percentage(
            self._device_gps_data.get("NetworkQuality")
        )

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
            if isinstance(battery_str, str):
                clean_str = "".join(c for c in battery_str if c.isdigit() or c == ".")
                if clean_str:
                    return float(clean_str) / 1000.0
            return None
        except (ValueError, TypeError):
            return None

    @property
    def odometer(self) -> float | None:
        """Return odometer reading in kilometers."""
        return safe_float(self._device_data.get("Odometer"))

    @property
    def report_frequency(self) -> int | None:
        """Return report frequency in seconds."""
        return safe_int(self._device_gps_data.get("ReportFrequency"))

    @property
    def bluetooth_enabled(self) -> bool:
        """Return True if Bluetooth is enabled on the device."""
        bluetooth_enabled = self._device_data_extra.get("terminal", {}).get(
            "BluetoothStatus", False
        )
        return bool(bluetooth_enabled)

    # -------------------------------------------------------------------------
    # Alert/state properties (read-only)
    # -------------------------------------------------------------------------

    @property
    def alarm_status(self) -> bool | None:
        """Return alarm status."""
        return self._device_data.get("AlarmStatus")

    @property
    def low_battery_alert_enabled(self) -> bool:
        """Return whether low battery alert is enabled."""
        # The API reports this as 0/1, not as a bool
        return bool(self._device_features_data.get("LowBatteryAlertEnabled", False))

    @property
    def geofence_enabled(self) -> bool | None:
        """Return aggregated geofence state for this device.

        True if all geofences are enabled, False if any is disabled, and None
        if the device has no geofences (or the state is not yet known).
        """
        return self._geofence_enabled

    def update_geofence_status(self, geofences: list[dict[str, Any]]) -> bool:
        """Update the aggregated geofence state from the full geofence list.

        The API returns every geofence for the account in one call; here we
        filter to this device (TerminalID) and collapse it to a single state.
        Returns True if the state changed.
        """
        terminal_geofences = [gf for gf in geofences if gf.get("TerminalID") == self.id]
        if not terminal_geofences:
            new_state: bool | None = None
        else:
            new_state = all(gf.get("Status") == "1" for gf in terminal_geofences)

        if new_state != self._geofence_enabled:
            self._geofence_enabled = new_state
            return True
        return False

    @property
    def low_battery_threshold(self) -> float | None:
        """Return low battery alert threshold in volts."""
        return safe_float(self._device_features_data.get("LowBatteryThreshold"))

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
        """Get the status of a digital output (used by binary sensor entities)."""
        state = self.get_digital_output_state(output_number)
        return state if state is not None else False

    def get_input_status(self, input_number: int) -> bool:
        """Get the status of a digital input (used by binary sensor entities)."""
        state = self.get_digital_input_state(input_number)
        return state if state is not None else False

    def get_digital_input_label(self, input_number: int) -> str | None:
        """Return the user-defined label for a digital input, if the API has one.

        Labels live in the edit-terminal response as DINsettings, keyed by the
        spelled-out input number ("DINTwoBtnLabel").
        """
        settings = self._device_data_extra.get("DINsettings") or []
        return self._get_io_label(settings, f"DIN{_ordinal_word(input_number)}BtnLabel")

    def get_digital_output_label(self, output_number: int) -> str | None:
        """Return the user-defined label for a digital output, if the API has one.

        Labels live in the edit-terminal response as relaySettings, keyed by the
        spelled-out output number ("DoutBtnLabelOne").
        """
        settings = self._device_data_extra.get("relaySettings") or []
        return self._get_io_label(
            settings, f"DoutBtnLabel{_ordinal_word(output_number)}"
        )

    @staticmethod
    def _get_io_label(settings: list[Any], key: str) -> str | None:
        """Pick a label out of the first I/O settings entry."""
        if not settings or not isinstance(settings[0], dict):
            return None
        label = settings[0].get(key)
        return label.strip() if isinstance(label, str) and label.strip() else None

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
        # The API spells this "SosAlarmEnabled"; the old "SoSAlarmEnabled" never matched.
        return bool(self._device_data_extra.get("SosAlarmEnabled", False))
