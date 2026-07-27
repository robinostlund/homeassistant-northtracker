"""Button platform for NorthTracker."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NorthTrackerConfigEntry, NorthTrackerDataUpdateCoordinator
from .devices import NorthTrackerGpsDevice
from .entity import NorthTrackerEntity

# All data comes from the coordinator, so there is no per-entity polling to limit.
PARALLEL_UPDATES = 0

BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="refresh",
    translation_key="refresh",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NorthTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NorthTracker button entities."""
    coordinator = entry.runtime_data

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
    """Representation of a NorthTracker refresh button."""

    entity_description = BUTTON_DESCRIPTION

    def __init__(
        self,
        coordinator: NorthTrackerDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)

        device = self.device
        # Use IMEI for stable unique_id
        identifier = device.imei if device else str(device_id)
        self._attr_unique_id = f"{identifier}_refresh"

    async def async_press(self) -> None:
        """Handle the button press - trigger a data refresh."""
        await self.coordinator.async_request_refresh()
