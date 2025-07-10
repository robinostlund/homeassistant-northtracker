"""Binary sensor platform for North-Tracker."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity

# Base binary sensor descriptions - these will be used as templates
BINARY_SENSOR_TEMPLATES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="input_status",
        translation_key="input",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the binary sensor platform and discover new entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    added_devices = set()

    def discover_binary_sensors() -> None:
        """Discover and add new binary sensors."""
        LOGGER.debug("Starting binary sensor discovery, current devices: %d", len(coordinator.data))
        new_entities = []
        for device_id, device in coordinator.data.items():
            if device_id not in added_devices:
                LOGGER.debug("Discovering binary sensors for new device: %s (ID: %d)", device.name, device_id)
                
                # Create binary sensors for each available digital input
                for input_num in device.available_inputs:
                    description = BinarySensorEntityDescription(
                        key=f"input_status_{input_num}",
                        translation_key=f"input_{input_num}",
                        device_class=BinarySensorDeviceClass.SAFETY,
                        name=f"Input {input_num}",
                    )
                    binary_sensor_entity = NorthTrackerBinarySensor(coordinator, device.id, description, input_num)
                    new_entities.append(binary_sensor_entity)
                    LOGGER.debug("Created binary sensor for input %d on device %s", input_num, device.name)
                
                added_devices.add(device_id)

        if new_entities:
            LOGGER.debug("Adding %d new binary sensor entities", len(new_entities))
            async_add_entities(new_entities)
        else:
            LOGGER.debug("No new binary sensor entities to add")

    entry.async_on_unload(coordinator.async_add_listener(discover_binary_sensors))
    discover_binary_sensors()


class NorthTrackerBinarySensor(NorthTrackerEntity, BinarySensorEntity):
    """Defines a North-Tracker binary sensor."""

    def __init__(
        self, 
        coordinator: NorthTrackerDataUpdateCoordinator, 
        device_id: int, 
        description: BinarySensorEntityDescription,
        input_number: int | None = None
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._input_number = input_number
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self._input_number is not None:
            # Dynamic input sensor
            return self.device.get_input_status(self._input_number)
        else:
            # Legacy property-based sensor
            return getattr(self.device, self.entity_description.key, None)