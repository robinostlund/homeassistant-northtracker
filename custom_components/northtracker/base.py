"""Base helpers for North-Tracker platform setup."""
from __future__ import annotations

from typing import Callable, TypeVar, Generic, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, DEVICE_NAME_MAX_LENGTH, ENTITY_ID_MAX_LENGTH
from .coordinator import NorthTrackerDataUpdateCoordinator

T = TypeVar('T')

class BasePlatformSetup(Generic[T]):
    """Base class for setting up North-Tracker platforms with common patterns."""
    
    def __init__(
        self,
        platform_name: str,
        entity_class: type[T],
        entity_descriptions: list[Any],
        create_entity_callback: Callable[[NorthTrackerDataUpdateCoordinator, int, Any], T]
    ):
        """Initialize base platform setup.
        
        Args:
            platform_name: Name of the platform (e.g., "sensor", "switch")
            entity_class: The entity class to create
            entity_descriptions: List of entity descriptions to check
            create_entity_callback: Function to create entity instances
        """
        self.platform_name = platform_name
        self.entity_class = entity_class
        self.entity_descriptions = entity_descriptions
        self.create_entity_callback = create_entity_callback
    
    async def async_setup_entry(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        async_add_entities: AddEntitiesCallback
    ) -> None:
        """Set up platform entities with common discovery pattern."""
        coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        added_devices: set[int] = set()

        def discover_entities() -> None:
            """Discover and add new entities."""
            new_entities = []
            
            for device_id, device in coordinator.data.items():
                if device_id not in added_devices:
                    for description in self.entity_descriptions:
                        if hasattr(description, 'exists_fn') and description.exists_fn and description.exists_fn(device):
                            entity = self.create_entity_callback(coordinator, device_id, description)
                            new_entities.append(entity)
                    
                    added_devices.add(device_id)
            
            if new_entities:
                async_add_entities(new_entities)

        entry.async_on_unload(coordinator.async_add_listener(discover_entities))
        discover_entities()


class AdvancedPlatformSetup(BasePlatformSetup[T]):
    """Advanced platform setup that supports custom entity creation logic.
    
    Useful for platforms like switch that need dynamic entity creation beyond
    simple entity descriptions.
    """
    
    def __init__(
        self,
        platform_name: str,
        entity_class: type[T],
        entity_descriptions: list[Any],
        create_entity_callback: Callable[[NorthTrackerDataUpdateCoordinator, int, Any], T],
        custom_entity_creator: Callable[[Any, int, Any, list[T]], None] | None = None
    ):
        """Initialize advanced platform setup.
        
        Args:
            platform_name: Name of the platform
            entity_class: The entity class to create
            entity_descriptions: List of entity descriptions 
            create_entity_callback: Function to create entity instances
            custom_entity_creator: Optional function to create custom entities
        """
        super().__init__(platform_name, entity_class, entity_descriptions, create_entity_callback)
        self.custom_entity_creator = custom_entity_creator
    
    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry, 
        async_add_entities: AddEntitiesCallback
    ) -> None:
        """Set up platform entities with advanced discovery pattern."""
        coordinator: NorthTrackerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        added_devices: set[int] = set()

        def discover_entities() -> None:
            """Discover and add new entities."""
            new_entities = []
            
            for device_id, device in coordinator.data.items():
                if device_id not in added_devices:
                    # Create custom entities (e.g., dynamic switches)
                    if self.custom_entity_creator:
                        self.custom_entity_creator(device, device_id, coordinator, new_entities)
                    
                    # Create standard entities from descriptions
                    for description in self.entity_descriptions:
                        if hasattr(description, 'exists_fn') and description.exists_fn and description.exists_fn(device):
                            entity = self.create_entity_callback(coordinator, device_id, description)
                            new_entities.append(entity)
                    
                    added_devices.add(device_id)
            
            if new_entities:
                async_add_entities(new_entities)
        
        entry.async_on_unload(coordinator.async_add_listener(discover_entities))
        discover_entities()


def validate_device_name(name: str) -> str:
    """Validate and truncate device name to maximum length.
    
    Args:
        name: Original device name
        
    Returns:
        Validated device name truncated to max length if necessary
    """
    if not name:
        return "Unknown Device"
    
    # Truncate if necessary
    if len(name) > DEVICE_NAME_MAX_LENGTH:
        truncated_name = name[:DEVICE_NAME_MAX_LENGTH-3] + "..."
        LOGGER.debug("Device name truncated from %d to %d characters: '%s' -> '%s'", 
                    len(name), len(truncated_name), name, truncated_name)
        return truncated_name
    
    return name


def validate_entity_id(entity_id: str) -> str:
    """Validate and truncate entity ID to Home Assistant limits.
    
    Args:
        entity_id: Original entity ID
        
    Returns:
        Validated entity ID truncated to max length if necessary
    """
    if not entity_id:
        return "unknown"
    
    # Home Assistant entity IDs have a 63 character limit
    if len(entity_id) > ENTITY_ID_MAX_LENGTH:
        truncated_id = entity_id[:ENTITY_ID_MAX_LENGTH]
        LOGGER.debug("Entity ID truncated from %d to %d characters: '%s' -> '%s'", 
                    len(entity_id), len(truncated_id), entity_id, truncated_id)
        return truncated_id
    
    return entity_id
