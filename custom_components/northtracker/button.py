"""Button platform for North-Tracker."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NorthTrackerDataUpdateCoordinator
from .entity import NorthTrackerEntity
from .devices import NorthTrackerGpsDevice
from .base import validate_entity_id


BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="refresh",
    translation_key="refresh",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up North-Tracker button entities."""
    coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NorthTrackerRefreshButton] = []

    for device_id, device in coordinator.data.items():
        # Only create refresh buttons for main GPS devices, not Bluetooth sensors
        if isinstance(device, NorthTrackerGpsDevice):
            entities.append(
                NorthTrackerRefreshButton(
                    coordinator=coordinator,
                    device_id=device_id,
                )
            )

    async_add_entities(entities)


class NorthTrackerRefreshButton(NorthTrackerEntity, ButtonEntity):
    """Representation of a North-Tracker refresh button."""

    entity_description = BUTTON_DESCRIPTION

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)
        
        device = self.device
        device_name = device.name if device else f"Device {device_id}"
        
        self._attr_unique_id = validate_entity_id(f"{device_id}_refresh")

    async def async_press(self) -> None:
        """Handle the button press - trigger a data refresh."""
        await self.coordinator.async_request_refresh()
