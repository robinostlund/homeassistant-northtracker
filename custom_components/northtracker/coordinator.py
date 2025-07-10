"""DataUpdateCoordinator for the North-Tracker integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NorthTracker, NorthTrackerDevice, APIError, AuthenticationError, RateLimitError
from .const import DOMAIN, LOGGER, DEFAULT_UPDATE_INTERVAL


class NorthTrackerDataUpdateCoordinator(DataUpdateCoordinator[dict[int, NorthTrackerDevice]]):
    """Class to manage fetching North-Tracker data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = NorthTracker(async_get_clientsession(hass))
        self.config_entry = entry
        
        # Validate and set update interval
        update_interval_minutes = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        if update_interval_minutes < 5:
            LOGGER.warning("Update interval too low (%d), setting to minimum of 5 minutes", update_interval_minutes)
            update_interval_minutes = 5
        elif update_interval_minutes > 1440:
            LOGGER.warning("Update interval too high (%d), setting to maximum of 1440 minutes", update_interval_minutes)
            update_interval_minutes = 1440
            
        update_interval = timedelta(minutes=update_interval_minutes)
        
        LOGGER.info("North-Tracker coordinator initialized with a %d minute update interval.", update_interval_minutes)

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[int, NorthTrackerDevice]:
        """Fetch data from API endpoint."""
        LOGGER.debug("Starting data update from North-Tracker API")
        try:
            # Authenticate only when needed (token management is handled in API class)
            if not self.api._token:
                await self.api.login(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD]
                )

            # 1. Get the base list of all devices
            resp_details = await self.api.get_all_units_details()
            if not resp_details.success:
                raise UpdateFailed("Failed to fetch device list from API")
            
            units = resp_details.data.get("units", [])
            LOGGER.debug("Successfully fetched base details, found %d units", len(units))

            # Create device objects from the base details
            devices = {unit_data['ID']: NorthTrackerDevice(self.api, unit_data) for unit_data in units}

            # 2. Get real-time location data
            try:
                resp_realtime = await self.api.get_realtime_tracking()
                if resp_realtime.success:
                    # Update each device with its location data
                    LOGGER.debug("Successfully fetched GPS details")
                    for gps_data in resp_realtime.data.get("gps", []):
                        device_id = gps_data.get("TrackerID")
                        if device_id in devices:
                            devices[device_id].update_gps_data(gps_data)
                else:
                    LOGGER.warning("Failed to fetch real-time location data")
            except Exception as err:
                LOGGER.warning("Error fetching real-time location data: %s", err)
                # Continue without GPS data rather than failing completely

            # 3. Fetch extra (non-location) details for each device in parallel
            async def update_device_details(device: NorthTrackerDevice) -> None:
                """Update a single device's details."""
                try:
                    await device.async_update()
                except Exception as err:
                    LOGGER.warning("Failed to update details for device %s: %s", device.name, err)
                    # Continue with other devices even if one fails

            # Update all devices in parallel with limited concurrency
            if devices:
                tasks = [update_device_details(device) for device in devices.values()]
                # Limit concurrent requests to avoid overwhelming the API
                semaphore = asyncio.Semaphore(5)
                
                async def limited_update(task):
                    async with semaphore:
                        await task
                
                await asyncio.gather(*[limited_update(task) for task in tasks], return_exceptions=True)
            
            LOGGER.debug("Successfully updated %d devices", len(devices))
            return devices

        except AuthenticationError as err:
            LOGGER.error("Authentication failed: %s", err)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except RateLimitError as err:
            LOGGER.warning("Rate limit exceeded: %s", err)
            raise UpdateFailed(f"Rate limit exceeded: {err}") from err
        except APIError as err:
            LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            LOGGER.exception("Unexpected error communicating with API")
            raise UpdateFailed(f"Unexpected error communicating with API: {err}") from err