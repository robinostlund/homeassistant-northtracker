---
applyTo: "custom_components/northtracker/translations/*.json"
---

# Translation Files Instructions

## Structure

Translation files follow Home Assistant's standard format:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to North-Tracker",
        "data": {
          "username": "Username",
          "password": "Password"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid authentication"
    }
  },
  "entity": {
    "sensor": {
      "sensor_key": {
        "name": "Sensor Name"
      }
    }
  }
}
```

## Adding New Translations

When adding new entities or config options:

1. Add to `en.json` (English - required)
2. Add to `sv.json` (Swedish)

## Entity Translations

Use `translation_key` in entity descriptions:

```python
# In sensor.py
SensorEntityDescription(
    key="battery_voltage",
    translation_key="battery_voltage",  # References translations
    ...
)
```

```json
// In translations/en.json
{
  "entity": {
    "sensor": {
      "battery_voltage": {
        "name": "Battery Voltage"
      }
    }
  }
}
```

## State Translations

For entities with specific states:

```json
{
  "entity": {
    "sensor": {
      "status": {
        "name": "Status",
        "state": {
          "online": "Online",
          "offline": "Offline",
          "unknown": "Unknown"
        }
      }
    }
  }
}
```

## Keep Both Languages in Sync

Always update both language files together. If unsure about Swedish translation, use English as placeholder with a TODO comment.
