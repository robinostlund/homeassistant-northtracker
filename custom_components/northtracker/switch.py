"""Switch platform for North-Tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, DEFAULT_BATTERY_LOW_THRESHOLD
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .api import NorthTrackerGpsDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerSwitchEntityDescription(SwitchEntityDescription):
    """Describes a North-Tracker switch entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerGpsDevice], Any] | None = None
    exists_fn: Callable[[NorthTrackerGpsDevice], bool] | None = None


STATIC_SWITCH_DESCRIPTIONS: tuple[NorthTrackerSwitchEntityDescription, ...] = (
    NorthTrackerSwitchEntityDescription(
        key="alarm_status",
        translation_key="alarm",
        icon="mdi:alarm-light",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda device: getattr(device, 'alarm_status', False),
        exists_fn=lambda device: hasattr(device, 'alarm_status') and getattr(device, 'alarm_status', None) is not None,
    ),
    NorthTrackerSwitchEntityDescription(
        key="low_battery_alert_enabled",
        translation_key="low_battery_alert",
        icon="mdi:battery-alert", 
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda device: device.low_battery_alert_enabled,
        exists_fn=lambda device: hasattr(device, 'low_battery_alert_enabled') and device.low_battery_alert_enabled is not None,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the switch platform and discover new entities."""
    from .base import AdvancedPlatformSetup
    
    def create_switch_entity(coordinator, device_id, description):
        """Create a switch entity instance."""
        return NorthTrackerSwitch(coordinator, device_id, description)
    
    def create_dynamic_switches(device, device_id: int, coordinator, new_entities: list) -> None:
        """Create dynamic switches for device inputs/outputs."""
        # Create switches for each available digital output
        if hasattr(device, 'available_outputs') and device.available_outputs:
            for output_num in device.available_outputs:
                description = NorthTrackerSwitchEntityDescription(
                    key=f"output_status_{output_num}",
                    translation_key=f"output_{output_num}",
                    device_class=SwitchDeviceClass.SWITCH,
                    name=f"Output {output_num}",
                )
                switch_entity = NorthTrackerSwitch(coordinator, device_id, description, output_number=output_num)
                new_entities.append(switch_entity)
                LOGGER.debug("Created switch for output %d on device %s", output_num, device.name)
        else:
            LOGGER.debug("No available outputs found for device %s", device.name)
        
        # Create switches for each available digital input (alert control)
        if hasattr(device, 'available_inputs') and device.available_inputs:
            for input_num in device.available_inputs:
                description = NorthTrackerSwitchEntityDescription(
                    key=f"input_status_{input_num}",
                    translation_key=f"input_{input_num}",
                    device_class=SwitchDeviceClass.SWITCH,
                    name=f"Input {input_num}",
                )
                switch_entity = NorthTrackerSwitch(coordinator, device_id, description, input_number=input_num)
                new_entities.append(switch_entity)
                LOGGER.debug("Created switch for input %d on device %s", input_num, device.name)
        else:
            LOGGER.debug("No available inputs found for device %s", device.name)
    
    # Use the advanced platform setup helper
    platform_setup = AdvancedPlatformSetup(
        platform_name="switch",
        entity_class=NorthTrackerSwitch,
        entity_descriptions=STATIC_SWITCH_DESCRIPTIONS,
        create_entity_callback=create_switch_entity,
        custom_entity_creator=create_dynamic_switches
    )
    
    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerSwitch(NorthTrackerEntity, SwitchEntity):
    """Defines a North-Tracker switch."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: NorthTrackerSwitchEntityDescription,
        output_number: int | None = None,
        input_number: int | None = None
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._output_number = output_number
        self._input_number = input_number
        self._attr_unique_id = validate_entity_id(f"{device_id}_{description.key}")
        # Track pending state changes to provide immediate feedback
        self._pending_state: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        # If we have a pending state change, use that for immediate feedback
        if self._pending_state is not None:
            return self._pending_state
            
        device = self.device
        if device is None:
            LOGGER.warning("Switch %s device is None, returning False", self.entity_description.key)
            return False
            
        if self._output_number is not None:
            # Dynamic output switch - use hasattr for safety
            if hasattr(device, 'get_output_status'):
                return device.get_output_status(self._output_number)
            else:
                LOGGER.warning("Device %s does not have get_output_status method", device.name)
                return False
        elif self._input_number is not None:
            # Dynamic input switch (alert status) - use hasattr for safety
            if hasattr(device, 'get_input_status'):
                return device.get_input_status(self._input_number)
            else:
                LOGGER.warning("Device %s does not have get_input_status method", device.name)
                return False
        else:
            # Static switch using value_fn if available
            if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
                return bool(self.entity_description.value_fn(device))
            else:
                # Fallback to getattr for backwards compatibility
                return bool(getattr(device, self.entity_description.key, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        device = self.device
        if device is None:
            LOGGER.error("Cannot turn on switch %s: device is None", self.entity_description.key)
            return
            
        LOGGER.debug("Attempting to turn ON switch %s for device %s", self.entity_description.key, device.name)
        
        if self._output_number is not None:
            # Dynamic output switch
            try:
                LOGGER.info("Turning ON output %d for device '%s'", self._output_number, device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = True
                self.async_write_ha_state()
                
                resp = await device.tracker.output_turn_on(device.id, self._output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn on output %d for device '%s': API returned success=False", self._output_number, device.name)
                    # Revert pending state on failure
                    self._pending_state = None
                    self.async_write_ha_state()
                else:
                    LOGGER.debug("Successfully sent turn ON command for output %d, device '%s'", self._output_number, device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning on output %d for device '%s': %s", self._output_number, device.name, err)
                # Revert pending state on error
                self._pending_state = None
                self.async_write_ha_state()
                # Continue and refresh anyway - entity state will reflect actual state
        elif self._input_number is not None:
            # Dynamic input switch (enable alert)
            try:
                LOGGER.info("Enabling alert for input %d on device '%s'", self._input_number, device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = True
                self.async_write_ha_state()
                
                resp = await device.tracker.input_turn_on(device.id, self._input_number)
                if not resp.success:
                    LOGGER.error("Failed to enable alert for input %d on device '%s': API returned success=False", self._input_number, device.name)
                    # Revert pending state on failure
                    self._pending_state = None
                    self.async_write_ha_state()
                else:
                    LOGGER.debug("Successfully enabled alert for input %d, device '%s'", self._input_number, device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error enabling alert for input %d on device '%s': %s", self._input_number, device.name, err)
                # Revert pending state on error
                self._pending_state = None
                self.async_write_ha_state()
                # Continue and refresh anyway - entity state will reflect actual state
        elif self.entity_description.key == "low_battery_alert_enabled":
            # Low battery alert toggle
            try:
                LOGGER.info("Enabling low battery alert for device '%s'", device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = True
                self.async_write_ha_state()
                
                # Get current threshold
                current_threshold = getattr(device, 'low_battery_threshold', None) or DEFAULT_BATTERY_LOW_THRESHOLD
                
                resp = await device.tracker.set_low_battery_alert(getattr(device, 'imei', ''), True, current_threshold)
                if not resp.success:
                    LOGGER.error("Failed to enable low battery alert for device '%s': API returned success=False", device.name)
                    # Revert pending state on failure
                    self._pending_state = None
                    self.async_write_ha_state()
                else:
                    LOGGER.debug("Successfully enabled low battery alert for device '%s'", device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error enabling low battery alert for device '%s': %s", device.name, err)
                # Revert pending state on error
                self._pending_state = None
                self.async_write_ha_state()
                # Continue and refresh anyway - entity state will reflect actual state
        else:
            # Legacy handling for other static switches (like alarm)
            LOGGER.warning("Turn on not implemented for static switch %s", self.entity_description.key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        device = self.device
        if device is None:
            LOGGER.error("Cannot turn off switch %s: device is None", self.entity_description.key)
            return
            
        LOGGER.debug("Attempting to turn OFF switch %s for device %s", self.entity_description.key, device.name)
        
        if self._output_number is not None:
            # Dynamic output switch
            try:
                LOGGER.info("Turning OFF output %d for device '%s'", self._output_number, device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = False
                self.async_write_ha_state()
                
                resp = await device.tracker.output_turn_off(device.id, self._output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn off output %d for device '%s': API returned success=False", self._output_number, device.name)
                    # Revert pending state on failure
                    self._pending_state = None
                    self.async_write_ha_state()
                else:
                    LOGGER.debug("Successfully sent turn OFF command for output %d, device '%s'", self._output_number, device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning off output %d for device '%s': %s", self._output_number, device.name, err)
                # Revert pending state on error
                self._pending_state = None
                self.async_write_ha_state()
                # Continue and refresh anyway - entity state will reflect actual state
        elif self._input_number is not None:
            # Dynamic input switch (disable alert)
            try:
                LOGGER.info("Disabling alert for input %d on device '%s'", self._input_number, device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = False
                self.async_write_ha_state()
                
                resp = await device.tracker.input_turn_off(device.id, self._input_number)
                if not resp.success:
                    LOGGER.error("Failed to disable alert for input %d on device '%s': API returned success=False", self._input_number, device.name)
                    # Revert pending state on failure
                    self._pending_state = None
                    self.async_write_ha_state()
                else:
                    LOGGER.debug("Successfully disabled alert for input %d, device '%s'", self._input_number, device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error disabling alert for input %d on device '%s': %s", self._input_number, device.name, err)
                # Revert pending state on error
                self._pending_state = None
                self.async_write_ha_state()
                # Continue and refresh anyway - entity state will reflect actual state
        elif self.entity_description.key == "low_battery_alert_enabled":
            # Low battery alert toggle
            try:
                LOGGER.info("Disabling low battery alert for device '%s'", device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = False
                self.async_write_ha_state()
                
                # Get current threshold
                current_threshold = getattr(device, 'low_battery_threshold', None) or DEFAULT_BATTERY_LOW_THRESHOLD
                
                resp = await device.tracker.set_low_battery_alert(getattr(device, 'imei', ''), False, current_threshold)
                if not resp.success:
                    LOGGER.error("Failed to disable low battery alert for device '%s': API returned success=False", device.name)
                    # Revert pending state on failure
                    self._pending_state = None
                    self.async_write_ha_state()
                else:
                    LOGGER.debug("Successfully disabled low battery alert for device '%s'", device.name)
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error disabling low battery alert for device '%s': %s", device.name, err)
                # Revert pending state on error
                self._pending_state = None
                self.async_write_ha_state()
                # Continue and refresh anyway - entity state will reflect actual state
        else:
            # Legacy handling for other static switches (like alarm)
            LOGGER.warning("Turn off not implemented for static switch %s", self.entity_description.key)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear pending state when coordinator provides fresh data
        if self._pending_state is not None:
            LOGGER.debug("Clearing pending state for switch %s after coordinator update", self.entity_description.key)
            self._pending_state = None
        super()._handle_coordinator_update()