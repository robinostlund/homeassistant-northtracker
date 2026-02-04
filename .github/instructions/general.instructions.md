---
applyTo: "**"
---

# North-Tracker Integration - Copilot Instructions

This is a custom Home Assistant integration for North-Tracker GPS tracking devices.

## Project Overview

- **Domain**: `northtracker`
- **Purpose**: GPS device tracking, I/O control, and Bluetooth sensor monitoring
- **Framework**: Home Assistant Custom Component
- **Language**: Python 3.11+

## Architecture

### Core Components

- `__init__.py` - Integration setup, entry points, and device cleanup
- `api.py` - North-Tracker REST API client with token authentication
- `coordinator.py` - Data update coordinator for polling device data
- `config_flow.py` - Configuration UI flow for setup and reconfiguration
- `const.py` - Constants, defaults, and configuration values
- `entity.py` - Base entity class with device info handling
- `helpers.py` - Utility functions
- `migrations.py` - Entity migration handling between versions

### Device Types (`devices/`)

- `base.py` - Abstract base device class
- `gps_device.py` - GPS tracker devices with full feature support
- `sensor_device.py` - Bluetooth sensors (temperature, door contact)

### Entity Platforms

- `sensor.py` - Sensor entities (battery, signal, speed, temperature, etc.)
- `binary_sensor.py` - Binary sensors (digital inputs, door sensors)
- `switch.py` - Switch entities (digital outputs)
- `button.py` - Button entities (manual refresh)
- `device_tracker.py` - GPS location tracking
- `number.py` - Number entities
- `diagnostics.py` - Diagnostic data export

## Coding Standards

### General Rules

- Always use `from __future__ import annotations` at the top of files
- Use type hints for all function parameters and return values
- Add docstrings to all classes and public methods
- Follow PEP 8 style guidelines
- Use `LOGGER` from `const.py` for logging, not direct `logging.getLogger()`

### Home Assistant Patterns

- Entities must inherit from `NorthTrackerEntity` base class
- Use `CoordinatorEntity` pattern for data updates
- Use `_attr_*` attributes for entity properties
- Set `_attr_has_entity_name = True` for proper naming
- Use `DeviceInfo` with IMEI as the stable identifier

### Entity Unique IDs

- Format: `{imei}_{entity_type}` or `{imei}_{entity_type}_{index}`
- Example: `123456789012345_battery_voltage`
- Always use IMEI (not device_id) for stable identifiers

### Error Handling

- Use custom exceptions from `api.py`: `NorthTrackerError`, `NorthTrackerAuthError`, `NorthTrackerApiError`
- Log errors with appropriate level and context
- Handle `ConfigEntryNotReady` for setup failures

### Translations

- Add all user-facing strings to `translations/en.json` and `translations/sv.json`
- Use translation keys in entity descriptions

## API Integration

- Base URL: `https://apiv2.northtracker.com/api/v1`
- Authentication: JWT token-based with automatic refresh
- Rate limiting: Respect API limits with exponential backoff
- Timeout: 30 seconds default

## Testing Considerations

- Test with both GPS devices and Bluetooth sensors
- Verify entity creation for dynamic I/O ports
- Test authentication flow and token refresh
- Check migration between versions
