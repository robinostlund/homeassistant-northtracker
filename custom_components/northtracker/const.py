"""Constants for the NorthTracker integration."""

from __future__ import annotations

from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "northtracker"
LOGGER = getLogger(__package__)

# Manufacturer and URLs
MANUFACTURER = "NorthTracker"
CONFIGURATION_URL = "https://gps.northtracker.com"

# Platforms. The integration is read-only: everything the API can change is
# configured in the NorthTracker web UI, so no controllable platforms here.
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
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
API_TIMEZONE = "Europe/Stockholm"  # timezone used by NorthTracker API
# Minimum time between re-authentications triggered by a 5xx response. A broken
# endpoint keeps answering 5xx, and logging in for every such request would hammer
# the login endpoint for no gain.
API_REAUTH_COOLDOWN = 300  # seconds
API_ERROR_BODY_PREVIEW_LENGTH = 500  # characters of a 5xx body to log
API_MAX_REALTIME_PAGES = 20  # safety stop when paging through real-time tracking data

# Device Constants
MAX_BLUETOOTH_SENSORS_PER_DEVICE = 9  # slots 1-9

# Signal Quality Thresholds
MIN_SIGNAL_STRENGTH = 0
MAX_SIGNAL_STRENGTH = 100
SIGNAL_SCALE_MIN = 0  # Minimum value on NorthTracker's 0-5 signal scale
SIGNAL_SCALE_MAX = 5  # Maximum value on NorthTracker's 0-5 signal scale
SIGNAL_EXCELLENT_THRESHOLD = 80
SIGNAL_GOOD_THRESHOLD = 60
SIGNAL_POOR_THRESHOLD = 40

# Logging Constants
LOGGER_TOKEN_PREVIEW_LENGTH = 10  # characters to show in token preview

# Utility Constants
GPS_COORDINATE_PRECISION = 6  # decimal places for GPS coordinates
DEVICE_NAME_MAX_LENGTH = 50  # maximum device name length for display

# Battery Voltage
MAX_BATTERY_VOLTAGE_READING = 50.0  # volts - maximum reasonable battery voltage reading
