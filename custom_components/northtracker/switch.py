"""Switch platform for North-Tracker."""
from __future__ import annotations
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity

SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="output_status_1",
        translation_key="output_1",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="output_status_2",
        translation_key="output_2",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="output_status_3",
        translation_key="output_3",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="alarm_status",
        translation_key="alarm",
        icon="mdi:alarm-light",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the switch platform and discover new entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    added_devices = set()

    def discover_switches() -> None:
        """Discover and add new switches."""
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                for description in SWITCH_DESCRIPTIONS:
                    if hasattr(device, description.key):
                        new_entities.append(NorthTrackerSwitch(coordinator, device.id, description))
                added_devices.add(device_id)
        
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(discover_switches))
    discover_switches()


class NorthTrackerSwitch(NorthTrackerEntity, SwitchEntity):
    """Defines a North-Tracker switch."""

    def __init__(self, coordinator: NorthTrackerDataUpdateCoordinator, device_id: int, description: SwitchEntityDescription) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return getattr(self.device, self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        output_map = {
            "output_status_1": 1,
            "output_status_2": 2,
            "output_status_3": 3,
        }
        output_number = output_map.get(self.entity_description.key)

        if output_number:
            try:
                LOGGER.info("Turning ON output %d for device '%s'", output_number, self.device.name)
                resp = await self.device.tracker.output_turn_on(self.device.id, output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn on output %d for device '%s'", output_number, self.device.name)
                    # Just log the error and refresh - don't raise exception
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning on output %d for device '%s': %s", output_number, self.device.name, err)
                # Continue and refresh anyway - entity state will reflect actual state

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        output_map = {
            "output_status_1": 1,
            "output_status_2": 2,
            "output_status_3": 3,
        }
        output_number = output_map.get(self.entity_description.key)
        
        if output_number:
            try:
                LOGGER.info("Turning OFF output %d for device '%s'", output_number, self.device.name)
                resp = await self.device.tracker.output_turn_off(self.device.id, output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn off output %d for device '%s'", output_number, self.device.name)
                    # Just log the error and refresh - don't raise exception
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning off output %d for device '%s': %s", output_number, self.device.name, err)
                # Continue and refresh anyway - entity state will reflect actual state