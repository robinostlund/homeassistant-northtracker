# Contributing to NorthTracker Integration

Thank you for your interest in contributing to the Home Assistant NorthTracker Integration!

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a feature branch: `git checkout -b feature/my-feature`
4. Make your changes
5. Add tests if applicable
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11+
- Home Assistant development environment
- Access to a NorthTracker device or API documentation

### Installing Dependencies

```bash
pip install -r requirements.txt
```

### Project Structure

```
custom_components/northtracker/
├── __init__.py          # Integration setup and entry points
├── api.py               # NorthTracker API client
├── base.py              # Base classes
├── coordinator.py       # Data update coordinator
├── config_flow.py       # Configuration UI flow
├── const.py             # Constants and configuration
├── entity.py            # Base entity classes
├── helpers.py           # Utility functions
├── migrations.py        # Entity migration handling
├── devices/             # Device type implementations
│   ├── base.py          # Base device class
│   ├── gps_device.py    # GPS tracker device
│   └── sensor_device.py # Bluetooth sensor device
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
├── switch.py            # Switch entities (digital outputs)
├── button.py            # Button entities
├── device_tracker.py    # Device tracker entity
├── number.py            # Number entities
└── diagnostics.py       # Diagnostic data export
```

## Debug Logging

Enable debug logging for development by adding to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.northtracker: debug
```

### Log Analysis

The integration provides detailed logging:

- **API Requests/Responses**: Masked sensitive data for security
- **Authentication Flow**: Token management and refresh cycles
- **Entity Discovery**: Dynamic I/O detection process
- **Performance Metrics**: Update timing and success rates

## Code Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Add docstrings for classes and public methods
- Keep functions focused and single-purpose

### Entity Development

When adding new entities:

1. Add constants to `const.py`
2. Create entity class in the appropriate platform file
3. Register entity in `__init__.py` PLATFORMS list
4. Add translations in `translations/` directory
5. Update `icons.json` if needed

### API Changes

When modifying API interactions:

1. Update `api.py` with new endpoints
2. Handle errors appropriately with `NorthTrackerError` subclasses
3. Add rate limiting considerations
4. Update `docs/API_DOCUMENTATION.md`

## Testing

### Manual Testing

1. Install the integration in a test Home Assistant instance
2. Configure with test credentials
3. Verify entity creation and updates
4. Test edge cases and error handling

### Log Verification

Check logs for:
- Successful authentication
- Entity discovery
- Data updates
- Error handling

## Creating a Release

Releases are automated via GitHub Actions. When you push a tag, the workflow will automatically:

- Update `manifest.json` with the tag version
- Create a release zip file
- Generate a changelog from merged PRs
- Publish a GitHub Release

### Steps to Release a New Version

```bash
# Make sure you're on main with latest changes
git checkout main
git pull

# Create and push a tag
git tag v2.1.0
git push origin v2.1.0
```

The release will be created automatically within a few minutes.

### Version Format

- Use semantic versioning: `v1.2.3`
- Pre-releases: `v1.2.3-beta1` or `v1.2.3-alpha1`

### Version Checklist

Before releasing:

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Translations are complete
- [ ] CHANGELOG entries are added (if maintaining manually)
- [ ] Breaking changes are documented

## Pull Request Guidelines

### Before Submitting

- Ensure your code follows the project style
- Update documentation if needed
- Add/update translations for new user-facing strings
- Test your changes thoroughly

### PR Description

Include in your PR description:

- What the change does
- Why it's needed
- How to test it
- Screenshots (for UI changes)
- Breaking changes (if any)

## API Documentation

For detailed API documentation, see [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md).

Key API features:

- **Token-based Authentication**: Secure JWT token management
- **Rate Limiting**: Respects API rate limits with exponential backoff
- **Error Handling**: Comprehensive error categorization and recovery
- **Parallel Processing**: Efficient device data fetching

## Questions?

- **Issues**: [GitHub Issues](https://github.com/robinostlund/homeassistant-northtracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/robinostlund/homeassistant-northtracker/discussions)

---

Thank you for contributing! 🎉
