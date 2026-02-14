"""Switch platform for NorthTracker."""

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

from .const import LOGGER, DEFAULT_BATTERY_LOW_THRESHOLD
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .devices import NorthTrackerBaseDevice, NorthTrackerGpsDevice
from .base import validate_entity_id


@dataclass(kw_only=True)
class NorthTrackerSwitchEntityDescription(SwitchEntityDescription):
    """Describes a NorthTracker switch entity with custom attributes."""

    value_fn: Callable[[NorthTrackerBaseDevice], Any] | None = None


# Switch descriptions for GPS devices
GPS_SWITCH_DESCRIPTIONS: tuple[NorthTrackerSwitchEntityDescription, ...] = (
    NorthTrackerSwitchEntityDescription(
        key="low_battery_alert_enabled",
        translation_key="low_battery_alert",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda device: device.low_battery_alert_enabled,
    ),
    NorthTrackerSwitchEntityDescription(
        key="geofence",
        translation_key="geofence",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch platform and discover new entities."""
    from .base import AdvancedPlatformSetup

    def create_switch_entity(coordinator, device_id, description):
        """Create a switch entity instance."""
        return NorthTrackerSwitch(coordinator, device_id, description)

    def create_dynamic_switches(
        device, device_id: int, coordinator, new_entities: list
    ) -> None:
        """Create dynamic switches for device inputs/outputs."""
        # Create switches for each available digital output
        if (
            device.capabilities.has_digital_outputs
            and hasattr(device, "available_outputs")
            and device.available_outputs
        ):
            for output_num in device.available_outputs:
                description = NorthTrackerSwitchEntityDescription(
                    key=f"output_status_{output_num}",
                    translation_key=f"output_{output_num}",
                    device_class=SwitchDeviceClass.SWITCH,
                    name=f"Output {output_num}",
                )
                switch_entity = NorthTrackerSwitch(
                    coordinator, device_id, description, output_number=output_num
                )
                new_entities.append(switch_entity)
                LOGGER.debug(
                    "Created switch for output %d on device %s", output_num, device.name
                )

        # Create switches for each available digital input (alert control)
        if (
            device.capabilities.has_digital_inputs
            and hasattr(device, "available_inputs")
            and device.available_inputs
        ):
            for input_num in device.available_inputs:
                description = NorthTrackerSwitchEntityDescription(
                    key=f"input_status_{input_num}",
                    translation_key=f"input_{input_num}",
                    device_class=SwitchDeviceClass.SWITCH,
                    name=f"Input {input_num}",
                )
                switch_entity = NorthTrackerSwitch(
                    coordinator, device_id, description, input_number=input_num
                )
                new_entities.append(switch_entity)
                LOGGER.debug(
                    "Created switch for input %d on device %s", input_num, device.name
                )

    # Use the advanced platform setup helper
    platform_setup = AdvancedPlatformSetup(
        platform_name="switch",
        entity_class=NorthTrackerSwitch,
        entity_descriptions=GPS_SWITCH_DESCRIPTIONS,
        create_entity_callback=create_switch_entity,
        custom_entity_creator=create_dynamic_switches,
    )

    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerSwitch(NorthTrackerEntity, SwitchEntity):
    """Defines a NorthTracker switch."""

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: NorthTrackerSwitchEntityDescription,
        output_number: int | None = None,
        input_number: int | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._output_number = output_number
        self._input_number = input_number
        # Use IMEI for stable unique_id
        device = self.device
        identifier = device.imei if device else str(device_id)
        self._attr_unique_id = validate_entity_id(f"{identifier}_{description.key}")
        # Track pending state changes to provide immediate feedback
        self._pending_state: bool | None = None
        # Initialize geofence state (will be updated in async_added_to_hass)
        self._geofence_state: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # For geofence switch, fetch the current status from API
        if self.entity_description.key == "geofence":
            device = self.device
            if device is not None:
                try:
                    status = await device.tracker.get_geofence_status_for_terminal(
                        device.id
                    )
                    if status is not None:
                        self._geofence_state = status
                        LOGGER.debug(
                            "Initialized geofence state for '%s': %s",
                            device.name,
                            status,
                        )
                        self.async_write_ha_state()
                except Exception as err:
                    LOGGER.warning(
                        "Failed to fetch initial geofence status for '%s': %s",
                        device.name,
                        err,
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
            return device.get_output_status(self._output_number)
        elif self._input_number is not None:
            return device.get_input_status(self._input_number)
        elif self.entity_description.key == "geofence":
            # Geofence alarm state - track via _geofence_state attribute
            return self._geofence_state or False
        elif self.entity_description.value_fn:
            # Use value_fn from entity description
            return bool(self.entity_description.value_fn(device))
        else:
            # Fallback to attribute on device
            return bool(getattr(device, self.entity_description.key, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_set_state(False)

    async def _async_set_state(self, enabled: bool) -> None:
        """Set the switch state with pending state handling."""
        device = self.device
        if device is None:
            return

        action = "on" if enabled else "off"

        if self._output_number is not None:
            await self._async_execute_api_call(
                enabled,
                device.tracker.output_turn_on(device.id, self._output_number)
                if enabled
                else device.tracker.output_turn_off(device.id, self._output_number),
                f"Failed to turn {action} output {self._output_number} for device '{device.name}'",
            )
        elif self._input_number is not None:
            await self._async_execute_api_call(
                enabled,
                device.tracker.input_turn_on(device.id, self._input_number)
                if enabled
                else device.tracker.input_turn_off(device.id, self._input_number),
                f"Failed to set input {self._input_number} alert {action} for device '{device.name}'",
            )
        elif self.entity_description.key == "low_battery_alert_enabled":
            current_threshold = (
                getattr(device, "low_battery_threshold", None)
                or DEFAULT_BATTERY_LOW_THRESHOLD
            )
            await self._async_execute_api_call(
                enabled,
                device.tracker.set_low_battery_alert(
                    device.imei, enabled, current_threshold
                ),
                f"Failed to set low battery alert {action} for device '{device.name}'",
            )
        elif self.entity_description.key == "geofence":
            await self._async_set_geofence(device, enabled)

    async def _async_execute_api_call(
        self, target_state: bool, api_call, error_msg: str
    ) -> None:
        """Execute an API call with pending state handling."""
        try:
            self._pending_state = target_state
            self.async_write_ha_state()

            resp = await api_call
            if not resp.success:
                LOGGER.error(error_msg)
                self._pending_state = None
                self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            LOGGER.error("%s: %s", error_msg, err)
            self._pending_state = None
            self.async_write_ha_state()

    async def _async_set_geofence(
        self, device: NorthTrackerGpsDevice, enabled: bool
    ) -> None:
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
                    LOGGER.warning(
                        "Failed to set geofence status for device '%s'", device.name
                    )
                    success = False

            if success:
                LOGGER.info(
                    "Successfully %s geofences for device '%s'",
                    "enabled" if enabled else "disabled",
                    device.name,
                )
            else:
                LOGGER.warning(
                    "Some geofence settings failed for device '%s'", device.name
                )

            await self.coordinator.async_request_refresh()

        except Exception as err:
            LOGGER.error(
                "Error setting geofences for device '%s': %s", device.name, err
            )
            self._pending_state = None
            self._geofence_state = not enabled  # Revert state on error
            self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear pending state when coordinator provides fresh data
        if self._pending_state is not None:
            self._pending_state = None
        super()._handle_coordinator_update()
