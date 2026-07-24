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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NorthTrackerConfigEntry, NorthTrackerDataUpdateCoordinator
from .devices import NorthTrackerBaseDevice
from .entity import NorthTrackerEntity


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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform and discover new entities."""
    from .base import BasePlatformSetup

    def create_binary_sensor_entity(coordinator, device_id, description):
        """Create a binary sensor entity instance."""
        return NorthTrackerBinarySensor(coordinator, device_id, description)

    # Use the generic platform setup helper
    platform_setup = BasePlatformSetup(
        platform_name="binary_sensor",
        entity_class=NorthTrackerBinarySensor,
        entity_descriptions=BINARY_SENSOR_DESCRIPTIONS,
        create_entity_callback=create_binary_sensor_entity,
    )

    await platform_setup.async_setup_entry(hass, entry, async_add_entities)


class NorthTrackerBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a NorthTracker binary sensor for both GPS and Bluetooth devices."""

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
        description: NorthTrackerBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        # Use IMEI for stable unique_id
        device = self.device
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

        # Use value_fn from entity description
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(device)
        return getattr(device, self.entity_description.key, None)
