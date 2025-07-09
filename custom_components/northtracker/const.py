"""Constants for the North-Tracker integration."""
from logging import getLogger

DOMAIN = "northtracker"
LOGGER = getLogger(__package__)

# Configuration Constants
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"

# Defaults
DEFAULT_UPDATE_INTERVAL = 15

# Platforms
PLATFORMS = ["sensor", "switch", "binary_sensor", "device_tracker"]