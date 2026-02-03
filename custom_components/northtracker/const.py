"""Constants for the North-Tracker integration."""
from __future__ import annotations

from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "northtracker"
LOGGER = getLogger(__package__)

# Manufacturer and URLs
MANUFACTURER = "North-Tracker"
CONFIGURATION_URL = "https://gps.northtracker.com"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Defaults
DEFAULT_UPDATE_INTERVAL = 15  # minutes

# Validation Constants
MIN_UPDATE_INTERVAL = 0.17  # 10 seconds in minutes (10/60 ≈ 0.17)
MAX_UPDATE_INTERVAL = 1440  # minutes

# API Constants
API_BASE_URL = "https://apiv2.northtracker.com/api/v1"
API_TIMEOUT = 30  # seconds
API_MAX_RETRIES = 3
API_RETRY_DELAY = 1  # seconds
API_RATE_LIMIT_WARNING_THRESHOLD = 80  # percent
API_TIMEZONE = "Europe/Stockholm"  # timezone used by North-Tracker API

# Device Constants  
MAX_BLUETOOTH_SENSORS_PER_DEVICE = 9  # slots 1-9

# Signal Quality Thresholds
MIN_SIGNAL_STRENGTH = 0
MAX_SIGNAL_STRENGTH = 100
SIGNAL_SCALE_MIN = 0  # Minimum value on North-Tracker's 0-5 signal scale
SIGNAL_SCALE_MAX = 5  # Maximum value on North-Tracker's 0-5 signal scale
SIGNAL_EXCELLENT_THRESHOLD = 80
SIGNAL_GOOD_THRESHOLD = 60
SIGNAL_POOR_THRESHOLD = 40

# Logging Constants
LOGGER_TOKEN_PREVIEW_LENGTH = 10  # characters to show in token preview

# Utility Constants
GPS_COORDINATE_PRECISION = 6  # decimal places for GPS coordinates
DEVICE_NAME_MAX_LENGTH = 50  # maximum device name length for display
ENTITY_ID_MAX_LENGTH = 63  # Home Assistant entity ID limit

# Default Values
DEFAULT_BATTERY_LOW_THRESHOLD = 20  # percent

# Battery Voltage Thresholds (for number entities)
MIN_BATTERY_VOLTAGE_THRESHOLD = 10.0  # volts - minimum allowed low battery voltage threshold
MAX_BATTERY_VOLTAGE_THRESHOLD = 30.0  # volts - maximum allowed low battery voltage threshold
MAX_BATTERY_VOLTAGE_READING = 50.0  # volts - maximum reasonable battery voltage reading