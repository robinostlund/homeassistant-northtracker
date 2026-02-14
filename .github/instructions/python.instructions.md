---
applyTo: "custom_components/northtracker/*.py"
---

# Python Code Instructions for NorthTracker

## File Structure

Every Python file should start with:

```python
"""Description of the module."""

from __future__ import annotations
```

## Imports Order

1. Standard library imports
2. Third-party imports (homeassistant)
3. Local imports (from . import)

Example:
```python
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
```

## Logging

Always use the shared logger:

```python
from .const import LOGGER

# Good
LOGGER.debug("Processing device %s", device_id)
LOGGER.error("Failed to connect: %s", error)

# Bad - don't create new loggers
import logging
logger = logging.getLogger(__name__)  # Don't do this
```

## Entity Creation

When creating new entities:

1. Inherit from `NorthTrackerEntity`
2. Set `_attr_has_entity_name = True`
3. Use `_attr_*` pattern for properties
4. Generate unique_id with IMEI prefix

```python
class NorthTrackerSensor(NorthTrackerEntity, SensorEntity):
    """NorthTracker sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        
        device = self.device
        if device:
            self._attr_unique_id = f"{device.imei}_{description.key}"
```

## Async Patterns

- Use `async def` for all Home Assistant callbacks
- Use `await` for async operations
- Never block the event loop

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    coordinator = NorthTrackerDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    return True
```

## Type Hints

Always include type hints:

```python
def get_device_name(device_id: int, default: str = "Unknown") -> str:
    """Get the device name."""
    ...

async def async_fetch_data(self) -> dict[str, Any]:
    """Fetch data from API."""
    ...
```

## Constants

Add new constants to `const.py`:

```python
# In const.py
NEW_CONSTANT = "value"
DEFAULT_TIMEOUT = 30

# Usage in other files
from .const import NEW_CONSTANT, DEFAULT_TIMEOUT
```

## Error Handling

Use specific exception types:

```python
from .api import NorthTrackerError, NorthTrackerAuthError, NorthTrackerApiError

try:
    await self.api.fetch_devices()
except NorthTrackerAuthError:
    LOGGER.error("Authentication failed")
    raise ConfigEntryAuthFailed
except NorthTrackerApiError as err:
    LOGGER.warning("API error: %s", err)
    raise UpdateFailed(str(err))
```
