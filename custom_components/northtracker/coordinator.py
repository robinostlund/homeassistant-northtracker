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
        
        LOGGER.info("North-Tracker coordinator initialized with a %s minute update interval.", update_interval.total_seconds() / 60)

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[int, NorthTrackerDevice]:
        """Fetch data from API endpoint."""
        LOGGER.debug("Starting data update from North-Tracker API")
        try:
            # Login on each update to ensure the token is fresh
            await self.api.login(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD]
            )

            # 1. Get the base list of all devices
            resp_details = await self.api.get_all_units_details()
            if not resp_details.success:
                raise UpdateFailed("Failed to fetch device list from API")
            
            units = resp_details.data.get("units", [])
            LOGGER.info("Successfully fetched base details, found %d units", len(units))

            # Create device objects from the base details
            devices = {unit_data['ID']: NorthTrackerDevice(self.api, unit_data) for unit_data in units}

            # 2. Get real-time location data
            resp_realtime = await self.api.get_realtime_tracking()
            if resp_realtime.success:
                # Update each device with its location data
                for gps_data in resp_realtime.data.get("gps", []):
                    device_id = gps_data.get("TrackerID")
                    if device_id in devices:
                        devices[device_id].update_gps_data(gps_data)

            # 3. Fetch extra (non-location) details for each device
            for device in devices.values():
                await device.async_update()
            
            return devices

        except Exception as err:
            # The coordinator will log the UpdateFailed exception automatically
            raise UpdateFailed(f"Error communicating with API: {err}") from err