---
applyTo: "custom_components/northtracker/sensor.py,custom_components/northtracker/binary_sensor.py,custom_components/northtracker/switch.py,custom_components/northtracker/button.py,custom_components/northtracker/number.py"
---

# Entity Platform Instructions

## Adding New Entity Types

When adding new sensors or entities to a platform file:

### 1. Define Entity Description

Add to the appropriate description list:

```python
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="new_sensor_key",
        translation_key="new_sensor_key",
        native_unit_of_measurement=UnitOfMeasurement.UNIT,
        device_class=SensorDeviceClass.CLASS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,  # if applicable
    ),
    # ... existing descriptions
)
```

### 2. Add Value Extraction

Add the value extraction logic in the entity's `native_value` or `is_on` property:

```python
@property
def native_value(self) -> StateType:
    """Return the sensor value."""
    device = self.device
    if not device:
        return None

    match self.entity_description.key:
        case "new_sensor_key":
            return device.new_property
        case _:
            return None
```

### 3. Update Translations

Add translation keys to both language files:

```json
// translations/en.json
{
  "entity": {
    "sensor": {
      "new_sensor_key": {
        "name": "New Sensor Name"
      }
    }
  }
}
```

### 4. Update Icons (if needed)

Add icon mapping to `icons.json`:

```json
{
  "entity": {
    "sensor": {
      "new_sensor_key": {
        "default": "mdi:icon-name"
      }
    }
  }
}
```

## Entity Categories

Use appropriate entity categories:

- `EntityCategory.CONFIG` - Configuration entities
- `EntityCategory.DIAGNOSTIC` - Diagnostic information
- `None` - Primary entities shown by default

## Dynamic Entity Creation

For entities that depend on device capabilities (like I/O ports):

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[Entity] = []

    for device in coordinator.devices.values():
        # Add standard entities
        for description in SENSOR_DESCRIPTIONS:
            entities.append(NorthTrackerSensor(coordinator, device.device_id, description))
        
        # Add dynamic entities based on device capabilities
        if hasattr(device, "digital_inputs"):
            for i, input_available in enumerate(device.digital_inputs, 1):
                if input_available:
                    entities.append(
                        NorthTrackerBinarySensor(coordinator, device.device_id, i)
                    )

    async_add_entities(entities)
```

## Device Type Checks

Check device type when creating entities:

```python
from .devices import NorthTrackerGPSDevice, NorthTrackerSensorDevice

for device in coordinator.devices.values():
    if isinstance(device, NorthTrackerGPSDevice):
        # Create GPS-specific entities
        ...
    elif isinstance(device, NorthTrackerSensorDevice):
        # Create Bluetooth sensor entities
        ...
```
