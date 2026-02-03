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
from .api import NorthTrackerGpsDevice, NorthTrackerSensorDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerSwitchEntityDescription(SwitchEntityDescription):
    """Describes a North-Tracker switch entity with custom attributes."""
    
    value_fn: Callable[[NorthTrackerGpsDevice], Any] | None = None
    exists_fn: Callable[[NorthTrackerGpsDevice], bool] | None = None


# Switch descriptions for GPS devices
GPS_SWITCH_DESCRIPTIONS: tuple[NorthTrackerSwitchEntityDescription, ...] = (
    NorthTrackerSwitchEntityDescription(
        key="alarm_status",
        translation_key="alarm",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda device: getattr(device, 'alarm_status', False),
        exists_fn=lambda device: hasattr(device, 'alarm_status') and getattr(device, 'alarm_status', None) is not None,
    ),
    NorthTrackerSwitchEntityDescription(
        key="low_battery_alert_enabled",
        translation_key="low_battery_alert",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda device: device.low_battery_alert_enabled,
        exists_fn=lambda device: hasattr(device, 'low_battery_alert_enabled') and device.low_battery_alert_enabled is not None,
    ),
    NorthTrackerSwitchEntityDescription(
        key="geofence",
        translation_key="geofence",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:map-marker-radius",
        # Geofence switch always exists for GPS devices
        exists_fn=lambda device: isinstance(device, NorthTrackerGpsDevice),
    ),
)

# BLE switch descriptions removed - API for magnet alarm not working correctly
# TODO: Re-add when API is fixed


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
        entity_descriptions=GPS_SWITCH_DESCRIPTIONS,
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
        # Use IMEI for stable unique_id (falls back to device_id if IMEI not available)
        device = self.device
        imei = device.imei if device and hasattr(device, 'imei') else str(device_id)
        self._attr_unique_id = validate_entity_id(f"{imei}_{description.key}")
        # Track pending state changes to provide immediate feedback
        self._pending_state: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        
        # For geofence switch, fetch the current status from API
        if self.entity_description.key == "geofence":
            device = self.device
            if device is not None:
                try:
                    status = await device.tracker.get_geofence_status_for_terminal(device.id)
                    if status is not None:
                        self._geofence_state = status
                        LOGGER.debug(
                            "Initialized geofence state for '%s': %s",
                            device.name, status
                        )
                        self.async_write_ha_state()
                except Exception as err:
                    LOGGER.warning(
                        "Failed to fetch initial geofence status for '%s': %s",
                        device.name, err
                    )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        # If we have a pending state change, use that for immediate feedback
        if self._pending_state is not None:
            return self._pending_state
            
        device = self.device
        if device is None:
            return False
            
        if self._output_number is not None:
            if hasattr(device, 'get_output_status'):
                return device.get_output_status(self._output_number)
            return False
        elif self._input_number is not None:
            if hasattr(device, 'get_input_status'):
                return device.get_input_status(self._input_number)
            return False
        elif self.entity_description.key == "geofence":
            # Geofence alarm state - track via _geofence_state attribute
            # If not initialized yet, default to None (unknown) then show False
            return getattr(self, '_geofence_state', None) or False
        else:
            # Static switch using value_fn if available
            if hasattr(self.entity_description, 'value_fn') and self.entity_description.value_fn:
                return bool(self.entity_description.value_fn(device))
            else:
                return bool(getattr(device, self.entity_description.key, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        device = self.device
        if device is None:
            return
        
        if self._output_number is not None:
            try:
                self._pending_state = True
                self.async_write_ha_state()
                
                resp = await device.tracker.output_turn_on(device.id, self._output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn on output %d for device '%s'", self._output_number, device.name)
                    self._pending_state = None
                    self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning on output %d for device '%s': %s", self._output_number, device.name, err)
                self._pending_state = None
                self.async_write_ha_state()
        elif self._input_number is not None:
            # Dynamic input switch (enable alert)
            try:
                LOGGER.info("Enabling alert for input %d on device '%s'", self._input_number, device.name)
                # Set pending state for immediate UI feedback
                self._pending_state = True
                self.async_write_ha_state()
                
                resp = await device.tracker.input_turn_on(device.id, self._input_number)
                if not resp.success:
                    LOGGER.error("Failed to enable alert for input %d on device '%s'", self._input_number, device.name)
                    self._pending_state = None
                    self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error enabling alert for input %d on device '%s': %s", self._input_number, device.name, err)
                self._pending_state = None
                self.async_write_ha_state()
        elif self.entity_description.key == "low_battery_alert_enabled":
            try:
                self._pending_state = True
                self.async_write_ha_state()
                
                current_threshold = getattr(device, 'low_battery_threshold', None) or DEFAULT_BATTERY_LOW_THRESHOLD
                resp = await device.tracker.set_low_battery_alert(getattr(device, 'imei', ''), True, current_threshold)
                if not resp.success:
                    LOGGER.error("Failed to enable low battery alert for device '%s'", device.name)
                    self._pending_state = None
                    self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error enabling low battery alert for device '%s': %s", device.name, err)
                self._pending_state = None
                self.async_write_ha_state()
        elif self.entity_description.key == "geofence":
            await self._async_set_geofence(device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        device = self.device
        if device is None:
            return
        
        if self._output_number is not None:
            try:
                self._pending_state = False
                self.async_write_ha_state()
                
                resp = await device.tracker.output_turn_off(device.id, self._output_number)
                if not resp.success:
                    LOGGER.error("Failed to turn off output %d for device '%s'", self._output_number, device.name)
                    self._pending_state = None
                    self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error turning off output %d for device '%s': %s", self._output_number, device.name, err)
                self._pending_state = None
                self.async_write_ha_state()
        elif self._input_number is not None:
            try:
                self._pending_state = False
                self.async_write_ha_state()
                
                resp = await device.tracker.input_turn_off(device.id, self._input_number)
                if not resp.success:
                    LOGGER.error("Failed to disable alert for input %d on device '%s'", self._input_number, device.name)
                    self._pending_state = None
                    self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error disabling alert for input %d on device '%s': %s", self._input_number, device.name, err)
                self._pending_state = None
                self.async_write_ha_state()
        elif self.entity_description.key == "low_battery_alert_enabled":
            try:
                self._pending_state = False
                self.async_write_ha_state()
                
                current_threshold = getattr(device, 'low_battery_threshold', None) or DEFAULT_BATTERY_LOW_THRESHOLD
                resp = await device.tracker.set_low_battery_alert(getattr(device, 'imei', ''), False, current_threshold)
                if not resp.success:
                    LOGGER.error("Failed to disable low battery alert for device '%s'", device.name)
                    self._pending_state = None
                    self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                LOGGER.error("Error disabling low battery alert for device '%s': %s", device.name, err)
                self._pending_state = None
                self.async_write_ha_state()
        elif self.entity_description.key == "geofence":
            await self._async_set_geofence(device, False)

    async def _async_set_geofence(self, device: NorthTrackerGpsDevice, enabled: bool) -> None:
        """Enable or disable all geofences for this GPS device."""
        action = "Enabling" if enabled else "Disabling"
        LOGGER.info("%s geofences for device '%s'", action, device.name)
        
        try:
            self._pending_state = enabled
            self._geofence_state = enabled
            self.async_write_ha_state()
            
            # Set all geofences for this device
            geofence_responses = await device.tracker.set_all_geofences_status(
                terminal_id=device.id,
                enabled=enabled,
            )
            
            success = True
            for resp in geofence_responses:
                if not resp.success:
                    LOGGER.warning("Failed to set geofence status for device '%s'", device.name)
                    success = False
            
            if success:
                LOGGER.info("Successfully %s geofences for device '%s'", 
                          "enabled" if enabled else "disabled", device.name)
            else:
                LOGGER.warning("Some geofence settings failed for device '%s'", device.name)
            
            await self.coordinator.async_request_refresh()
            
        except Exception as err:
            LOGGER.error("Error setting geofences for device '%s': %s", device.name, err)
            self._pending_state = None
            self._geofence_state = not enabled  # Revert state on error
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear pending state when coordinator provides fresh data
        if self._pending_state is not None:
            self._pending_state = None
        super()._handle_coordinator_update()