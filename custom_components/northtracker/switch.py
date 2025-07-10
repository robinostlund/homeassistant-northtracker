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
        LOGGER.debug("Starting switch discovery, current devices: %d", len(coordinator.data))
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                LOGGER.debug("Discovering switches for new device: %s (ID: %d)", device.name, device_id)
                for description in SWITCH_DESCRIPTIONS:
                    if hasattr(device, description.key):
                        switch_entity = NorthTrackerSwitch(coordinator, device.id, description)
                        new_entities.append(switch_entity)
                        LOGGER.debug("Created switch: %s for device %s", description.key, device.name)
                    else:
                        LOGGER.debug("Device %s does not have attribute %s, skipping switch", device.name, description.key)
                added_devices.add(device_id)
        
        if new_entities:
            LOGGER.debug("Adding %d new switch entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new switch entities to add")

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
        LOGGER.debug("Attempting to turn ON switch %s for device %s", self.entity_description.key, self.device.name)
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
                    LOGGER.error("Failed to turn on output %d for device '%s': API returned success=False", output_number, self.device.name)
                    # Just log the error and refresh - don't raise exception
                else:
                    LOGGER.debug("Successfully sent turn ON command for output %d, device '%s'", output_number, self.device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning on output %d for device '%s': %s", output_number, self.device.name, err)
                # Continue and refresh anyway - entity state will reflect actual state
        else:
            LOGGER.warning("No output mapping found for switch %s", self.entity_description.key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        LOGGER.debug("Attempting to turn OFF switch %s for device %s", self.entity_description.key, self.device.name)
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
                    LOGGER.error("Failed to turn off output %d for device '%s': API returned success=False", output_number, self.device.name)
                    # Just log the error and refresh - don't raise exception
                else:
                    LOGGER.debug("Successfully sent turn OFF command for output %d, device '%s'", output_number, self.device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning off output %d for device '%s': %s", output_number, self.device.name, err)
                # Continue and refresh anyway - entity state will reflect actual state
        else:
            LOGGER.warning("No output mapping found for switch %s", self.entity_description.key)