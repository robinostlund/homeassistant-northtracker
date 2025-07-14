"""Constants for the North-Tracker integration."""
from __future__ import annotations

from logging import getLogger

DOMAIN = "northtracker"
LOGGER = getLogger(__package__)

# Configuration Constants
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Defaults
DEFAULT_UPDATE_INTERVAL = 15  # minutes

# Validation Constants
MIN_UPDATE_INTERVAL = 0.17  # 10 seconds in minutes (10/60 ≈ 0.17)
MAX_UPDATE_INTERVAL = 1440  # minutes

# Platforms
PLATFORMS = ["sensor", "switch", "binary_sensor", "device_tracker", "number"]