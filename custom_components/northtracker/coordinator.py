"""DataUpdateCoordinator for the North-Tracker integration."""
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NorthTracker, NorthTrackerDevice
from .const import DOMAIN, LOGGER, DEFAULT_UPDATE_INTERVAL

class NorthTrackerDataUpdateCoordinator(DataUpdateCoordinator[dict[int, NorthTrackerDevice]]):
    """Class to manage fetching North-Tracker data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = NorthTracker(async_get_clientsession(hass))
        self.config_entry = entry
        update_interval = timedelta(minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL))

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[int, NorthTrackerDevice]:
        """Fetch data from API endpoint."""
        try:
            # Login on each update to ensure the token is fresh
            await self.api.login(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD]
            )

            # Get all device details
            resp = await self.api.get_all_units_details()
            if not resp.success:
                raise UpdateFailed("Failed to fetch device list")
            
            devices = {}
            for unit_data in resp.data.get("units", []):
                device = NorthTrackerDevice(self.api, unit_data)
                await device.async_update() # Fetch extra details for each device
                devices[device.id] = device
            
            return devices

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err