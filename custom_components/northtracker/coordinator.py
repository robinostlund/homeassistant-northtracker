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

from .api import NorthTracker, NorthTrackerGpsDevice, NorthTrackerSensorDevice, APIError, AuthenticationError, RateLimitError
from .const import DOMAIN, LOGGER, DEFAULT_UPDATE_INTERVAL, MIN_UPDATE_INTERVAL, MAX_UPDATE_INTERVAL


class NorthTrackerDataUpdateCoordinator(DataUpdateCoordinator[dict[int, NorthTrackerGpsDevice]]):
    """Class to manage fetching North-Tracker data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = NorthTracker(async_get_clientsession(hass))
        self.config_entry = entry
        
        # Validate config entry has required data
        if not entry.data:
            LOGGER.error("Config entry has no data - this indicates a corrupted configuration")
            raise ValueError("Invalid config entry: no data found")
            
        # Check for required credentials
        has_username = CONF_USERNAME in entry.data or "username" in entry.data or "user" in entry.data
        has_password = CONF_PASSWORD in entry.data or "password" in entry.data
        
        if not has_username or not has_password:
            LOGGER.error("Config entry missing required credentials. Available keys: %s", list(entry.data.keys()))
            raise ValueError("Invalid config entry: missing credentials")
        
        # Validate and set update interval
        update_interval_minutes = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        if update_interval_minutes < MIN_UPDATE_INTERVAL:
            LOGGER.warning("Update interval too low (%.2f), setting to minimum of %.2f minutes", update_interval_minutes, MIN_UPDATE_INTERVAL)
            update_interval_minutes = MIN_UPDATE_INTERVAL
        elif update_interval_minutes > MAX_UPDATE_INTERVAL:
            LOGGER.warning("Update interval too high (%.2f), setting to maximum of %.2f minutes", update_interval_minutes, MAX_UPDATE_INTERVAL)
            update_interval_minutes = MAX_UPDATE_INTERVAL
            
        update_interval = timedelta(minutes=update_interval_minutes)
        
        LOGGER.info("North-Tracker coordinator initialized with a %.2f minute update interval.", update_interval_minutes)

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)
        
        # Track devices that have actually changed data to avoid unnecessary entity updates
        self._devices_with_changes: set[int] = set()

    def device_has_changes(self, device_id: int) -> bool:
        """Check if a device has changes that require entity updates."""
        return device_id in self._devices_with_changes

    async def _async_update_data(self) -> dict[int, NorthTrackerGpsDevice]:
        """Fetch data from API endpoint."""
        start_time = datetime.now()
        LOGGER.debug("Starting coordinator data update")
        
        # Reset the devices with changes set at the start of each update
        self._devices_with_changes.clear()
        
        # Debug: Log config entry data to understand the structure
        LOGGER.debug("Config entry data keys: %s", list(self.config_entry.data.keys()))
        LOGGER.debug("Config entry data: %s", {k: "***" if "password" in k.lower() else v for k, v in self.config_entry.data.items()})
        
        try:
            # Authenticate only when needed (token management is handled in API class)
            if not self.api._token:
                LOGGER.debug("No token available, performing initial authentication")
                
                # Handle potential key name variations
                username = None
                password = None
                
                # Try Home Assistant standard constants first
                if CONF_USERNAME in self.config_entry.data:
                    username = self.config_entry.data[CONF_USERNAME]
                    password = self.config_entry.data[CONF_PASSWORD]
                # Fallback to potential alternative key names
                elif "username" in self.config_entry.data:
                    username = self.config_entry.data["username"]
                    password = self.config_entry.data["password"]
                elif "user" in self.config_entry.data:
                    username = self.config_entry.data["user"]
                    password = self.config_entry.data["password"]
                
                if not username or not password:
                    LOGGER.error("Unable to find username/password in config entry. Available keys: %s", list(self.config_entry.data.keys()))
                    raise UpdateFailed("Configuration error: missing credentials")
                
                LOGGER.debug("Found credentials, username: %s", username)
                await self.api.login(username, password)
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
            devices = {}
            for unit_data in units:
                device_type = unit_data.get('DeviceType', '').lower()
                device_id = unit_data.get('ID')
                device_name = unit_data.get('NameOnly', 'Unknown')
                
                if device_id is None:
                    LOGGER.warning("Unit data missing ID field, skipping: %s", unit_data)
                    continue
                
                # Only create devices for explicitly supported DeviceTypes
                if device_type == 'gps':
                    try:
                        device = NorthTrackerGpsDevice(self.api, unit_data)
                        devices[device_id] = device
                        LOGGER.debug("Created GPS device: ID %s (%s)", device_id, device.name)
                    except Exception as err:
                        LOGGER.error("Failed to create GPS device for ID %s: %s", device_id, err)
                        continue
                        
                elif device_type == 'sensor':
                    # Sensor devices will be created as NorthTrackerSensorDevice from GPS device's PairedSensors
                    # Note: If we ever want to support standalone sensors (not connected via PairedSensors),
                    # we could create NorthTrackerSensorDevice(self.api, unit_data) here instead
                    LOGGER.debug("Skipping standalone sensor unit %s (ID: %s) - sensors are created from GPS device's PairedSensors", 
                               device_name, device_id)
                    continue
                    
                else:
                    # Unknown device type - log and skip
                    LOGGER.info("Skipping unit %s (ID: %s) - unsupported DeviceType: %s", 
                              device_name, device_id, device_type)
                    continue
                    
            LOGGER.debug("Successfully created %d device objects", len(devices))
            
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
                        if device_id is None:
                            LOGGER.warning("GPS data missing TrackerID field, skipping: %s", gps_data)
                            continue
                            
                        if device_id in devices:
                            # Track if GPS data actually changed
                            try:
                                if devices[device_id].update_gps_data(gps_data):
                                    self._devices_with_changes.add(device_id)
                                    LOGGER.debug("GPS data changed for device ID %s", device_id)
                                else:
                                    LOGGER.debug("GPS data unchanged for device ID %s", device_id)
                            except Exception as err:
                                LOGGER.error("Error updating GPS data for device ID %s: %s", device_id, err)
                        else:
                            LOGGER.warning("Received GPS data for unknown device ID %s", device_id)
                else:
                    LOGGER.warning("Failed to fetch real-time location data")
            except Exception as err:
                LOGGER.warning("Error fetching real-time location data: %s", err)
                # Continue without GPS data rather than failing completely

            # Create virtual Bluetooth sensor devices AFTER GPS data is updated
            # so that latest_sensor_data is available
            bluetooth_devices_count = 0
            for main_device in list(devices.values()):  # Use list() to avoid dictionary change during iteration
                if main_device.available_bluetooth_sensors:
                    LOGGER.debug("Creating virtual Bluetooth devices for %s", main_device.name)
                    for bt_sensor in main_device.available_bluetooth_sensors:
                        try:
                            bt_device = NorthTrackerSensorDevice(main_device, bt_sensor)
                            devices[bt_device.id] = bt_device
                            bluetooth_devices_count += 1
                            LOGGER.debug("Created virtual Bluetooth device: %s (ID %s, PairedSlot %d)", 
                                       bt_device.name, bt_device.id, bt_device._paired_slot)
                        except Exception as err:
                            LOGGER.error("Failed to create Bluetooth device for sensor %s: %s", 
                                       bt_sensor.get("name", "unknown"), err)
            
            if bluetooth_devices_count > 0:
                LOGGER.debug("Successfully created %d virtual Bluetooth device objects", bluetooth_devices_count)

            # Log device capabilities for debugging
            for device in devices.values():
                if hasattr(device, 'available_inputs'):  # Main GPS device
                    LOGGER.debug("Device %s capabilities: inputs=%s, outputs=%s", 
                               device.name, device.available_inputs, device.available_outputs)
                else:  # Sensor device
                    LOGGER.debug("Sensor device %s (ID: %s, PairedSlot: %s, serial: %s)", 
                               device.name, device.id, device._paired_slot, device.serial_number)

            # 3. Fetch extra (non-location) details for each device in parallel
            # Only update main GPS/tracker devices, not Bluetooth sensors (they get data from their parent device)
            async def update_device_details(device: NorthTrackerGpsDevice) -> None:
                """Update a single device's details."""
                try:
                    # Track if device data actually changed
                    if await device.async_update():
                        self._devices_with_changes.add(device.id)
                        LOGGER.debug("Device details changed for device %s", device.name)
                    else:
                        LOGGER.debug("Device details unchanged for device %s", device.name)
                except Exception as err:
                    LOGGER.warning("Failed to update details for device %s (ID: %s): %s", device.name, device.id, err)
                    # Continue with other devices even if one fails

            # Update all devices in parallel with limited concurrency, but only main GPS devices
            # Only GPS devices can be updated via the edit-terminal API
            # Bluetooth sensors and other device types get their data from their parent device
            main_devices = [device for device in devices.values() 
                          if device.device_type == "gps"]
            excluded_count = len(devices) - len(main_devices)
            if main_devices:
                LOGGER.debug("Starting parallel device detail updates for %d GPS devices (excluding %d other devices)", 
                           len(main_devices), excluded_count)
                tasks = [update_device_details(device) for device in main_devices]
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
            
            # Log summary of devices with changes
            if self._devices_with_changes:
                LOGGER.debug("Devices with data changes: %s", list(self._devices_with_changes))
            else:
                LOGGER.debug("No devices had data changes - entity updates will be skipped")
            
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