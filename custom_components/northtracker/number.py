"""Number platform for North-Tracker."""
from __future__ import annotations
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity

# Number entity descriptions
NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="low_battery_threshold",
        translation_key="low_battery_threshold",
        mode=NumberMode.BOX,
        native_min_value=10.0,
        native_max_value=30.0,
        native_step=0.1,
        native_unit_of_measurement="V",
        icon="mdi:battery-alert",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the number platform and discover new entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    added_devices = set()

    def discover_numbers() -> None:
        """Discover and add new number entities."""
        LOGGER.debug("Starting number discovery, current devices: %d", len(coordinator.data))
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                LOGGER.debug("Discovering numbers for new device: %s (ID: %d)", device.name, device_id)
                
                # Add number entities that exist for all devices
                for description in NUMBER_DESCRIPTIONS:
                    if hasattr(device, description.key):
                        number_entity = NorthTrackerNumber(coordinator, device.id, description)
                        new_entities.append(number_entity)
                        LOGGER.debug("Created number entity: %s for device %s", description.key, device.name)
                    else:
                        LOGGER.debug("Device %s does not have attribute %s, skipping number entity", device.name, description.key)
                
                added_devices.add(device_id)

        if new_entities:
            LOGGER.debug("Adding %d new number entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new number entities to add")

    entry.async_on_unload(coordinator.async_add_listener(discover_numbers))
    discover_numbers()


class NorthTrackerNumber(NorthTrackerEntity, NumberEntity):
    """Defines a North-Tracker number entity."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.available:
            LOGGER.debug("Number entity %s not available", self.entity_description.key)
            return None
            
        device = self.device
        if device is None:
            LOGGER.debug("Number entity %s device is None", self.entity_description.key)
            return None
            
        value = getattr(device, self.entity_description.key, None)
        LOGGER.debug("Number entity %s for device %s has value: %s", self.entity_description.key, device.name, value)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        device = self.device
        if device is None:
            LOGGER.error("Cannot set value for number entity %s: device is None", self.entity_description.key)
            return
            
        LOGGER.debug("Setting %s to %.1f for device %s", self.entity_description.key, value, device.name)
        
        if self.entity_description.key == "low_battery_threshold":
            try:
                # Get current enabled status
                current_enabled = device.low_battery_alert_enabled
                
                # Set the new threshold while keeping the current enabled status
                resp = await device.tracker.set_low_battery_alert(device.imei, current_enabled, value)
                if not resp.success:
                    LOGGER.error("Failed to set low battery threshold to %.1f for device '%s': API returned success=False", 
                               value, device.name)
                else:
                    LOGGER.debug("Successfully set low battery threshold to %.1f for device '%s'", value, device.name)
                    # Request refresh to update the UI
                    await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error setting low battery threshold to %.1f for device '%s': %s", 
                           value, device.name, err)
        else:
            LOGGER.warning("Set value not implemented for number entity %s", self.entity_description.key)
