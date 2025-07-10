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

# Base switch descriptions - alarm is still static
STATIC_SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
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
                
                # Create switches for each available digital output
                for output_num in device.available_outputs:
                    description = SwitchEntityDescription(
                        key=f"output_status_{output_num}",
                        translation_key=f"output_{output_num}",
                        device_class=SwitchDeviceClass.SWITCH,
                        name=f"Output {output_num}",
                    )
                    switch_entity = NorthTrackerSwitch(coordinator, device.id, description, output_num)
                    new_entities.append(switch_entity)
                    LOGGER.debug("Created switch for output %d on device %s", output_num, device.name)
                
                # Add static switches (like alarm) that exist for all devices
                for description in STATIC_SWITCH_DESCRIPTIONS:
                    if hasattr(device, description.key):
                        switch_entity = NorthTrackerSwitch(coordinator, device.id, description)
                        new_entities.append(switch_entity)
                        LOGGER.debug("Created static switch: %s for device %s", description.key, device.name)
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

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: SwitchEntityDescription,
        output_number: int | None = None
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._output_number = output_number
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        if self._output_number is not None:
            # Dynamic output switch
            return self.device.get_output_status(self._output_number)
        else:
            # Legacy property-based switch (like alarm)
            return getattr(self.device, self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        LOGGER.debug("Attempting to turn ON switch %s for device %s", self.entity_description.key, self.device.name)
        
        if self._output_number is not None:
            # Dynamic output switch
            try:
                LOGGER.info("Turning ON output %d for device '%s'", self._output_number, self.device.name)
                resp = await self.device.tracker.output_turn_on(self.device.id, self._output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn on output %d for device '%s': API returned success=False", self._output_number, self.device.name)
                    # Just log the error and refresh - don't raise exception
                else:
                    LOGGER.debug("Successfully sent turn ON command for output %d, device '%s'", self._output_number, self.device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning on output %d for device '%s': %s", self._output_number, self.device.name, err)
                # Continue and refresh anyway - entity state will reflect actual state
        else:
            # Legacy handling for static switches (like alarm)
            LOGGER.warning("Turn on not implemented for static switch %s", self.entity_description.key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        LOGGER.debug("Attempting to turn OFF switch %s for device %s", self.entity_description.key, self.device.name)
        
        if self._output_number is not None:
            # Dynamic output switch
            try:
                LOGGER.info("Turning OFF output %d for device '%s'", self._output_number, self.device.name)
                resp = await self.device.tracker.output_turn_off(self.device.id, self._output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn off output %d for device '%s': API returned success=False", self._output_number, self.device.name)
                    # Just log the error and refresh - don't raise exception
                else:
                    LOGGER.debug("Successfully sent turn OFF command for output %d, device '%s'", self._output_number, self.device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning off output %d for device '%s': %s", self._output_number, self.device.name, err)
                # Continue and refresh anyway - entity state will reflect actual state
        else:
            # Legacy handling for static switches (like alarm)
            LOGGER.warning("Turn off not implemented for static switch %s", self.entity_description.key)