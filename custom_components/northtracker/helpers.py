"""Helper functions for North-Tracker integration."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .const import (
    LOGGER,
    API_TIMEZONE,
    GPS_COORDINATE_PRECISION,
    SIGNAL_EXCELLENT_THRESHOLD,
    SIGNAL_GOOD_THRESHOLD,
    SIGNAL_POOR_THRESHOLD,
)


def generate_stable_id(serial_number: str) -> int:
    """Generate a stable unique integer ID from a serial number string.
    
    Uses a hash to create a deterministic ID that:
    - Is always the same for the same serial number
    - Won't collide with GPS device IDs (uses high number range)
    - Fits within Python's int range
    
    Args:
        serial_number: The Bluetooth sensor's serial number from the API
        
    Returns:
        A stable unique integer ID
    """
    # Use MD5 hash (fast, deterministic) and take first 8 bytes as int
    # This gives us a large unique number that won't collide with GPS device IDs
    hash_bytes = hashlib.md5(serial_number.encode()).digest()[:8]
    # Use a high base to ensure we're in a different range than GPS device IDs
    # GPS device IDs are typically small (< 100000), so we use 10^9 as offset
    return int.from_bytes(hash_bytes, 'big') % (10**9) + 10**9


def parse_northtracker_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse a North-Tracker timestamp string to datetime with correct timezone.
    
    North-Tracker API returns timestamps in local timezone (Europe/Stockholm)
    even though they appear to be naive timestamps.
    
    Args:
        timestamp_str: Timestamp string from API (e.g., "2025-07-21 13:57:32")
        
    Returns:
        datetime object with correct timezone or None if parsing fails
    """
    if not timestamp_str:
        return None
    
    try:
        naive_dt = datetime.fromisoformat(timestamp_str)
        return naive_dt.replace(tzinfo=ZoneInfo(API_TIMEZONE))
    except (ValueError, TypeError) as err:
        LOGGER.warning("Invalid timestamp format: %s (%s)", timestamp_str, err)
        return None


def get_signal_quality_text(signal_percentage: int | None) -> str:
    """Get human-readable signal quality text based on percentage.
    
    Args:
        signal_percentage: Signal strength as percentage (0-100%)
        
    Returns:
        Human-readable signal quality text
    """
    if signal_percentage is None:
        return "Unknown"
    
    if signal_percentage >= SIGNAL_EXCELLENT_THRESHOLD:
        return "Excellent"
    elif signal_percentage >= SIGNAL_GOOD_THRESHOLD:
        return "Good"
    elif signal_percentage >= SIGNAL_POOR_THRESHOLD:
        return "Fair"
    else:
        return "Poor"


def round_gps_coordinate(coordinate: float | None) -> float | None:
    """Round GPS coordinate to configured precision.
    
    Args:
        coordinate: GPS coordinate (latitude or longitude)
        
    Returns:
        Rounded coordinate or None if input was None
    """
    if coordinate is None:
        return None
    
    return round(coordinate, GPS_COORDINATE_PRECISION)


def safe_int(value: Any, default: int | None = None) -> int | None:
    """Safely convert a value to int.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails (default: None)
        
    Returns:
        Integer value or default if conversion fails
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert a value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails (default: None)
        
    Returns:
        Float value or default if conversion fails
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
