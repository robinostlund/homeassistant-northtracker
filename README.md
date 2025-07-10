# Home Assistant North-Tracker Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/robinostlund/homeassistant-northtracker)](https://github.com/robinostlund/homeassistant-northtracker/releases)
[![GitHub](https://img.shields.io/github/license/robinostlund/homeassistant-northtracker)](LICENSE)

A custom Home Assistant integration for North-Tracker GPS tracking devices, providing comprehensive device monitoring, I/O control, and location tracking capabilities.

## Features

- **Device Tracking**: Real-time GPS location tracking with device tracker entities
- **Dynamic I/O Discovery**: Automatic detection and creation of entities for available digital inputs and outputs
- **Sensor Monitoring**: 
  - Battery voltage and percentage
  - Signal strength (RSSI)
  - Speed and altitude tracking
  - Engine hours and mileage
  - Temperature monitoring
- **Switch Control**: Digital output control for connected devices
- **Binary Sensors**: Digital input monitoring with configurable names
- **Comprehensive Logging**: Detailed debug logging for troubleshooting
- **Authentication Management**: Secure token-based authentication with automatic refresh
- **Reconfiguration Support**: Easy credential and settings updates through the UI

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL: `https://github.com/robinostlund/homeassistant-northtracker`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "North-Tracker" and install
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
3. Search for **"North-Tracker"**
4. Enter your North-Tracker credentials:
   - **Host**: Your North-Tracker server URL (e.g., `https://yourserver.com`)
   - **Username**: Your North-Tracker username
   - **Password**: Your North-Tracker password
   - **Update Interval**: How often to fetch data (20-300 seconds, default: 30)

### Reconfiguration

To update your credentials or settings:

1. Go to **Settings** → **Devices & Services**
2. Find your North-Tracker integration
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
- **Attributes**: Speed, altitude, course, accuracy

### Sensors
- **Battery Voltage**: Current battery voltage
- **Battery Percentage**: Calculated battery percentage
- **Signal Strength**: RSSI signal strength
- **Speed**: Current speed
- **Altitude**: Current altitude
- **Engine Hours**: Total engine runtime
- **Mileage**: Total distance traveled
- **Temperature**: Device temperature (if available)

### Switches (Digital Outputs)
- **Output 1-8**: Control digital outputs (created dynamically based on device capabilities)

### Binary Sensors (Digital Inputs)
- **Input 1-8**: Monitor digital inputs (created dynamically based on device capabilities)

## Device Support

The integration automatically discovers available I/O ports for each device:

- **Digital Inputs**: Automatically detected and created as binary sensors
- **Digital Outputs**: Automatically detected and created as switches
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
- Check that your North-Tracker server is accessible
- Ensure your account has API access

#### Missing Entities
- Check device capabilities in the integration logs
- Verify I/O ports are properly configured on your device
- Some entities may not be available for all device models

#### Update Issues
- Check your network connection
- Verify the update interval is not too aggressive
- Review logs for specific error messages

### Log Analysis

The integration provides detailed logging:

- **API Requests/Responses**: Masked sensitive data
- **Authentication Flow**: Token management and refresh
- **Entity Discovery**: Dynamic I/O detection
- **Performance Metrics**: Update timing and success rates

## API Documentation

The integration uses the North-Tracker REST API with the following key features:

- **Token-based Authentication**: Secure JWT token management
- **Rate Limiting**: Respects API rate limits with exponential backoff
- **Error Handling**: Comprehensive error categorization and recovery
- **Parallel Processing**: Efficient device data fetching

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/robinostlund/homeassistant-northtracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/robinostlund/homeassistant-northtracker/discussions)
- **Home Assistant Community**: [Community Forum](https://community.home-assistant.io/)

## Changelog

### Version 1.0.0
- Initial release
- Dynamic I/O discovery
- Comprehensive logging
- Authentication management
- Reconfiguration support
- Bug fixes for AttributeError and KeyError issues

---

**Note**: This integration is not officially affiliated with North-Tracker. It is a community-developed integration for Home Assistant users.