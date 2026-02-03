"""Diagnostics support for North-Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import NorthTrackerDataUpdateCoordinator

# Keys to redact from diagnostics output
TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "imei",
    "serial_number",
    "latitude",
    "longitude",
    "address",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Build device information
    devices_info = {}
    for device_id, device in coordinator.data.items():
        device_info = {
            "id": device_id,
            "name": device.name,
            "model": getattr(device, "model", None),
            "device_type": getattr(device, "device_type", None),
            "available": getattr(device, "available", None),
            "imei": getattr(device, "imei", None),
            "serial_number": getattr(device, "serial_number", None),
        }

        # Add GPS-specific info if available
        if hasattr(device, "has_position"):
            device_info["has_position"] = device.has_position
            device_info["latitude"] = getattr(device, "latitude", None)
            device_info["longitude"] = getattr(device, "longitude", None)
            device_info["gps_signal"] = getattr(device, "gps_signal", None)
            device_info["network_signal"] = getattr(device, "network_signal", None)
            device_info["speed"] = getattr(device, "speed", None)

        # Add battery info if available
        if hasattr(device, "battery_voltage"):
            device_info["battery_voltage"] = getattr(device, "battery_voltage", None)
        if hasattr(device, "battery_percentage"):
            device_info["battery_percentage"] = getattr(device, "battery_percentage", None)

        # Add sensor-specific info
        if hasattr(device, "temperature"):
            device_info["temperature"] = getattr(device, "temperature", None)
        if hasattr(device, "humidity"):
            device_info["humidity"] = getattr(device, "humidity", None)

        # Add last seen
        if hasattr(device, "last_seen") and device.last_seen:
            device_info["last_seen"] = device.last_seen.isoformat()

        devices_info[str(device_id)] = device_info

    # Build API info
    api_info = {
        "is_authenticated": coordinator.api.is_authenticated,
        "rate_limit": coordinator.api.rate_limit,
        "rate_limit_remaining": coordinator.api.rate_limit_remaining,
    }

    diagnostics_data = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
            "device_count": len(coordinator.data),
        },
        "api": api_info,
        "devices": async_redact_data(devices_info, TO_REDACT),
    }

    return diagnostics_data
