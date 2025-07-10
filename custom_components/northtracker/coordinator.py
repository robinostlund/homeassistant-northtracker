"""DataUpdateCoordinator for the North-Tracker integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

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
        LOGGER.debug("Starting coordinator data update")
        start_time = datetime.now()
        
        try:
            # Authenticate only when needed (token management is handled in API class)
            if not self.api._token:
                LOGGER.debug("No token available, performing initial authentication")
                await self.api.login(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD]
                )
            else:
                LOGGER.debug("Using existing token (expires: %s)", self.api._token_expires)

            # 1. Get the base list of all devices
            LOGGER.debug("Fetching all units details from API")
            resp_details = await self.api.get_all_units_details()
            if not resp_details.success:
                LOGGER.error("Failed to fetch device list from API")
                raise UpdateFailed("Failed to fetch device list from API")
            
            units = resp_details.data.get("units", [])
            LOGGER.debug("Successfully fetched base details, found %d units", len(units))
            
            # Log device summaries
            for unit in units[:3]:  # Log first 3 devices for debugging
                LOGGER.debug("Device found: ID=%s, Name=%s, Type=%s", 
                           unit.get("ID"), unit.get("NameOnly"), unit.get("DeviceType"))

            # Create device objects from the base details
            devices = {unit_data['ID']: NorthTrackerDevice(self.api, unit_data) for unit_data in units}
            LOGGER.debug("Created %d device objects", len(devices))
            
            # Log device capabilities for debugging
            for device in devices.values():
                LOGGER.debug("Device %s capabilities: inputs=%s, outputs=%s", 
                           device.name, device.available_inputs, device.available_outputs)

            # 2. Get real-time location data
            try:
                LOGGER.debug("Fetching real-time tracking data")
                resp_realtime = await self.api.get_realtime_tracking()
                if resp_realtime.success:
                    gps_data_list = resp_realtime.data.get("gps", [])
                    LOGGER.debug("Successfully fetched GPS details for %d devices", len(gps_data_list))
                    
                    # Update each device with its location data
                    for gps_data in gps_data_list:
                        device_id = gps_data.get("TrackerID")
                        if device_id in devices:
                            devices[device_id].update_gps_data(gps_data)
                            LOGGER.debug("Updated GPS data for device ID %d", device_id)
                        else:
                            LOGGER.warning("Received GPS data for unknown device ID %d", device_id)
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
                    LOGGER.debug("Successfully updated details for device %s", device.name)
                except Exception as err:
                    LOGGER.warning("Failed to update details for device %s: %s", device.name, err)
                    # Continue with other devices even if one fails

            # Update all devices in parallel with limited concurrency
            if devices:
                LOGGER.debug("Starting parallel device detail updates for %d devices", len(devices))
                tasks = [update_device_details(device) for device in devices.values()]
                # Limit concurrent requests to avoid overwhelming the API
                semaphore = asyncio.Semaphore(5)
                
                async def limited_update(task):
                    async with semaphore:
                        await task
                
                await asyncio.gather(*[limited_update(task) for task in tasks], return_exceptions=True)
                LOGGER.debug("Completed parallel device detail updates")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            LOGGER.debug("Successfully updated %d devices in %.2f seconds", len(devices), duration)
            
            return devices

        except AuthenticationError as err:
            LOGGER.error("Authentication failed: %s", err)
            # Trigger reauth flow
            self.config_entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except RateLimitError as err:
            LOGGER.warning("Rate limit exceeded: %s", err)
            raise UpdateFailed(f"Rate limit exceeded: {err}") from err
        except APIError as err:
            LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            LOGGER.exception("Unexpected error communicating with API")
            raise UpdateFailed(f"Unexpected error communicating with API: {err}") from err