"""Number platform for North-Tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER, MIN_BATTERY_VOLTAGE_THRESHOLD, MAX_BATTERY_VOLTAGE_THRESHOLD
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .devices import NorthTrackerBaseDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerNumberEntityDescription(NumberEntityDescription):
    """Describes a North-Tracker number entity with custom attributes."""

    value_fn: Callable[[NorthTrackerBaseDevice], Any] | None = None


# Number entity descriptions
NUMBER_DESCRIPTIONS: tuple[NorthTrackerNumberEntityDescription, ...] = (
    NorthTrackerNumberEntityDescription(
        key="low_battery_threshold",
        translation_key="low_battery_threshold",
        mode=NumberMode.BOX,
        native_min_value=MIN_BATTERY_VOLTAGE_THRESHOLD,
        native_max_value=MAX_BATTERY_VOLTAGE_THRESHOLD,
        native_step=0.1,
        native_unit_of_measurement="V",
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.low_battery_threshold,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the number platform and discover new entities."""
    from .base import BasePlatformSetup
    
    def create_number_entity(coordinator, device_id, description):
        """Create a number entity instance."""
        return NorthTrackerNumber(coordinator, device_id, description)
    
    # Use the generic platform setup helper
    platform_setup = BasePlatformSetup(
        platform_name="number",
        entity_class=NorthTrackerNumber,
        entity_descriptions=NUMBER_DESCRIPTIONS,
        create_entity_callback=create_number_entity
    )
    
    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerNumber(NorthTrackerEntity, NumberEntity):
    """Defines a North-Tracker number entity."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: NorthTrackerNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = validate_entity_id(f"{device_id}_{description.key}")

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.available:
            return None
            
        device = self.device
        if device is None:
            return None
            
        # Use value_fn from entity description
        if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
            return self.entity_description.value_fn(device)
        return getattr(device, self.entity_description.key, None)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        device = self.device
        if device is None:
            return
        
        if self.entity_description.key == "low_battery_threshold":
            try:
                current_enabled = getattr(device, 'low_battery_alert_enabled', False)
                resp = await device.tracker.set_low_battery_alert(getattr(device, 'imei', ''), current_enabled, value)
                if not resp.success:
                    LOGGER.error("Failed to set low battery threshold for device '%s'", device.name)
                else:
                    await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error setting low battery threshold for device '%s': %s", device.name, err)
