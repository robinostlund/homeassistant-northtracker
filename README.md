# Home Assistant NorthTracker Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/robinostlund/homeassistant-northtracker)](https://github.com/robinostlund/homeassistant-northtracker/releases)
[![GitHub](https://img.shields.io/github/license/robinostlund/homeassistant-northtracker)](LICENSE)

A custom Home Assistant integration for NorthTracker GPS tracking devices, providing device monitoring, I/O status and location tracking.

> **Read-only integration.** The integration only reads from the NorthTracker API. Digital outputs, alert settings and geofences are configured in the NorthTracker web UI, and their state is reported here. Earlier versions exposed switches and a number entity for this; those are removed and their leftover entities are deleted automatically on upgrade.

## Features

- **Device Tracking**: Real-time GPS location tracking with device tracker entities
- **Dynamic I/O Discovery**: Automatic detection of available digital inputs and outputs, reported as binary sensors with the labels you set in the web UI
- **Bluetooth Sensor Support**: External Bluetooth sensors (temperature, humidity, door/magnetic contact)
- **Sensor Monitoring**:
  - Battery voltage
  - GPS and network signal strength
  - Speed and odometer
  - Report frequency and last seen
  - Temperature and humidity (Bluetooth sensors)
- **Binary Sensors**: Digital I/O status, Bluetooth enabled, low battery alert, geofence state and Bluetooth door sensors
- **Button Controls**: Manual refresh trigger (local, no data is written to the API)
- **Comprehensive Logging**: Detailed debug logging for troubleshooting
- **Authentication Management**: Secure token-based authentication with automatic refresh
- **Reconfiguration Support**: Easy credential and settings updates through the UI
- **Automatic Migration**: Seamless entity migration when upgrading between versions

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL: `https://github.com/robinostlund/homeassistant-northtracker`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "NorthTracker" and install
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/robinostlund/homeassistant-northtracker/releases)
2. Extract the contents
3. Copy the `custom_components/northtracker` directory to your Home Assistant `custom_components` directory
4. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"NorthTracker"**
4. Enter your NorthTracker credentials:
  - **Username**: Your NorthTracker username
  - **Password**: Your NorthTracker password
   - **Update Interval**: How often to fetch data (20-300 seconds, default: 30)

### Reconfiguration

To update your credentials or settings:

1. Go to **Settings** → **Devices & Services**
2. Find your NorthTracker integration
3. Click the three dots and select **"Reconfigure"**
4. Update your settings as needed

### Re-authentication

If your credentials expire or change:

1. The integration will automatically prompt for re-authentication
2. Follow the notification to update your credentials
3. Or manually trigger re-auth from the integration settings

## Entities

The integration creates various entities based on your device capabilities:

### Device Tracker
- **Location**: Real-time GPS coordinates
- **Attributes**: Course, GPS accuracy, location status

### Sensors
- **Battery Voltage**: Current battery voltage
- **Odometer**: Total distance traveled
- **GPS Signal** / **Network Signal**: Signal strength in percent, with a quality attribute
- **Speed**: Current speed
- **Report Frequency**: How often the device reports in
- **Last Seen**: Timestamp of the last report
- **Low Battery Threshold**: The alert threshold configured in the web UI
- **Temperature** / **Humidity** / **Battery**: Bluetooth sensor readings

### Binary Sensors
- **Input {number}**: Digital input state (created dynamically, named after the label in the web UI)
- **Output {number}**: Digital output state (created dynamically, named after the label in the web UI)
- **Bluetooth Enabled**: Whether Bluetooth is enabled on the tracker
- **Low Battery Alert**: Whether the low battery alert is enabled
- **Geofence Alarm**: On when every geofence for the device is enabled
- **Door Sensor**: Bluetooth magnetic contact sensor (open/closed state)

### Buttons
- **Refresh**: Manually trigger a data update for the device

### Bluetooth Sensors
External Bluetooth sensors paired with your GPS device are automatically discovered:
- **Temperature and humidity**: Ambient readings
- **Battery**: Percentage and voltage
- **Door/Magnetic Sensor**: Open/closed state for doors, gates, etc.

## Device Support

The integration supports two types of devices:

### GPS Tracker Devices
Main tracking units with full feature support:
- Real-time location tracking
- Digital I/O monitoring
- Battery and signal monitoring
- Speed and odometer tracking

### Bluetooth Sensors
External sensors paired with GPS devices:
- **Temperature and humidity sensors**: Ambient monitoring
- **Door sensors**: Open/closed state detection
- Automatic discovery via GPS device pairing

The integration automatically discovers available I/O ports for each device:

- **Digital Inputs and Outputs**: Automatically detected and created as binary sensors
- **Backward Compatibility**: Works with existing configurations

## Troubleshooting

### Enable Debug Logging

Add the following to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.northtracker: debug
```

### Common Issues

#### Authentication Errors
- Verify your credentials are correct
- Check that your NorthTracker server is accessible
- Ensure your account has API access

#### Missing Entities
- Check device capabilities in the integration logs
- Verify I/O ports are properly configured on your device
- Some entities may not be available for all device models

#### Update Issues
- Check your network connection
- Verify the update interval is not too aggressive
- Review logs for specific error messages

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding guidelines, and release procedures.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/robinostlund/homeassistant-northtracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/robinostlund/homeassistant-northtracker/discussions)
- **Home Assistant Community**: [Community Forum](https://community.home-assistant.io/)

---

**Note**: This integration is not officially affiliated with NorthTracker. It is a community-developed integration for Home Assistant users.