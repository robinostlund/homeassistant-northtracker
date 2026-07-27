"""Binary sensor platform for NorthTracker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import NorthTrackerConfigEntry, NorthTrackerDataUpdateCoordinator
from .devices import NorthTrackerBaseDevice
from .entity import NorthTrackerEntity

# All data comes from the coordinator, so there is no per-entity polling to limit.
PARALLEL_UPDATES = 0


@dataclass(kw_only=True)
class NorthTrackerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a NorthTracker binary sensor entity with custom attributes."""

    value_fn: Callable[[NorthTrackerBaseDevice], Any] | None = None


# Unified binary sensor descriptions for both main GPS devices and Bluetooth sensors
BINARY_SENSOR_DESCRIPTIONS: tuple[NorthTrackerBinarySensorEntityDescription, ...] = (
    # GPS/tracker device binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="bluetooth_enabled",
        translation_key="bluetooth_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.bluetooth_enabled,
    ),
    NorthTrackerBinarySensorEntityDescription(
        key="low_battery_alert_enabled",
        translation_key="low_battery_alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.low_battery_alert_enabled,
    ),
    NorthTrackerBinarySensorEntityDescription(
        key="geofence_enabled",
        translation_key="geofence",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.geofence_enabled,
    ),
    # Bluetooth sensor binary sensors
    NorthTrackerBinarySensorEntityDescription(
        key="door_sensor",
        translation_key="door_sensor",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda device: (
            not device.magnetic_contact
        ),  # Invert: True=closed->False, False=open->True
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NorthTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform and discover new entities."""
    from .base import AdvancedPlatformSetup

    def create_binary_sensor_entity(coordinator, device_id, description):
        """Create a binary sensor entity instance."""
        return NorthTrackerBinarySensor(coordinator, device_id, description)

    def create_digital_io_sensors(
        device, device_id: int, coordinator, new_entities: list
    ) -> None:
        """Create binary sensors for the device's digital inputs and outputs."""
        if device.capabilities.has_digital_inputs:
            for input_num in getattr(device, "available_inputs", []):
                description = NorthTrackerBinarySensorEntityDescription(
                    key=f"input_status_{input_num}",
                    translation_key="digital_input",
                )
                new_entities.append(
                    NorthTrackerBinarySensor(
                        coordinator, device_id, description, input_number=input_num
                    )
                )
                LOGGER.debug(
                    "Created binary sensor for input %d on device %s",
                    input_num,
                    device.name,
                )

        if device.capabilities.has_digital_outputs:
            for output_num in getattr(device, "available_outputs", []):
                description = NorthTrackerBinarySensorEntityDescription(
                    key=f"output_status_{output_num}",
                    translation_key="digital_output",
                )
                new_entities.append(
                    NorthTrackerBinarySensor(
                        coordinator, device_id, description, output_number=output_num
                    )
                )
                LOGGER.debug(
                    "Created binary sensor for output %d on device %s",
                    output_num,
                    device.name,
                )

    platform_setup = AdvancedPlatformSetup(
        platform_name="binary_sensor",
        entity_class=NorthTrackerBinarySensor,
        entity_descriptions=BINARY_SENSOR_DESCRIPTIONS,
        create_entity_callback=create_binary_sensor_entity,
        custom_entity_creator=create_digital_io_sensors,
    )

    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a NorthTracker binary sensor for both GPS and Bluetooth devices."""

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: NorthTrackerBinarySensorEntityDescription,
        input_number: int | None = None,
        output_number: int | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._input_number = input_number
        self._output_number = output_number

        device = self.device
        # Prefer the label configured in the NorthTracker web UI ("Kylskåp"), and
        # fall back to the translated "Input/Output {number}" naming.
        label = None
        if device is not None and input_number is not None:
            label = device.get_digital_input_label(input_number)
        elif device is not None and output_number is not None:
            label = device.get_digital_output_label(output_number)

        if label:
            self._attr_name = label
        elif input_number is not None:
            self._attr_translation_placeholders = {"number": str(input_number)}
        elif output_number is not None:
            self._attr_translation_placeholders = {"number": str(output_number)}

        # Use IMEI for stable unique_id
        identifier = device.imei if device else str(device_id)
        self._attr_unique_id = f"{identifier}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if not self.available:
            return None

        device = self.device
        if device is None:
            return None

        if self._input_number is not None:
            return device.get_digital_input_state(self._input_number)
        if self._output_number is not None:
            return device.get_digital_output_state(self._output_number)

        # Use value_fn from entity description
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(device)
        return getattr(device, self.entity_description.key, None)
