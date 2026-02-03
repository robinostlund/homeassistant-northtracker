"""DataUpdateCoordinator for the North-Tracker integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import NorthTracker, APIError, AuthenticationError, RateLimitError
from .devices import NorthTrackerGpsDevice, NorthTrackerSensorDevice
from .const import (
    DOMAIN,
    LOGGER,
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
)


class NorthTrackerDataUpdateCoordinator(
    DataUpdateCoordinator[dict[int, NorthTrackerGpsDevice]]
):
    """Class to manage fetching North-Tracker data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = NorthTracker(async_get_clientsession(hass))

        # Validate config entry has required data
        if not entry.data:
            LOGGER.error(
                "Config entry has no data - this indicates a corrupted configuration"
            )
            raise ValueError("Invalid config entry: no data found")

        # Check for required credentials
        has_username = (
            CONF_USERNAME in entry.data
            or "username" in entry.data
            or "user" in entry.data
        )
        has_password = CONF_PASSWORD in entry.data or "password" in entry.data

        if not has_username or not has_password:
            LOGGER.error(
                "Config entry missing required credentials. Available keys: %s",
                list(entry.data.keys()),
            )
            raise ValueError("Invalid config entry: missing credentials")

        # Validate and set update interval
        update_interval_minutes = entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        if update_interval_minutes < MIN_UPDATE_INTERVAL:
            LOGGER.warning(
                "Update interval too low (%.2f), setting to minimum of %.2f minutes",
                update_interval_minutes,
                MIN_UPDATE_INTERVAL,
            )
            update_interval_minutes = MIN_UPDATE_INTERVAL
        elif update_interval_minutes > MAX_UPDATE_INTERVAL:
            LOGGER.warning(
                "Update interval too high (%.2f), setting to maximum of %.2f minutes",
                update_interval_minutes,
                MAX_UPDATE_INTERVAL,
            )
            update_interval_minutes = MAX_UPDATE_INTERVAL

        update_interval = timedelta(minutes=update_interval_minutes)

        LOGGER.info(
            "North-Tracker coordinator initialized with a %.2f minute update interval.",
            update_interval_minutes,
        )

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

        # Track devices that have actually changed data to avoid unnecessary entity updates
        self._devices_with_changes: set[int] = set()

    def device_has_changes(self, device_id: int) -> bool:
        """Check if a device has changes that require entity updates."""
        return device_id in self._devices_with_changes

    async def _async_update_data(self) -> dict[int, NorthTrackerGpsDevice]:
        """Fetch data from API endpoint."""
        start_time = datetime.now()

        # Reset the devices with changes set at the start of each update
        self._devices_with_changes.clear()

        try:
            # Authenticate only when needed (token management is handled in API class)
            if not self.api.is_authenticated:
                # Handle potential key name variations
                username = (
                    self.config_entry.data.get(CONF_USERNAME)
                    or self.config_entry.data.get("username")
                    or self.config_entry.data.get("user")
                )
                password = self.config_entry.data.get(
                    CONF_PASSWORD
                ) or self.config_entry.data.get("password")

                if not username or not password:
                    raise UpdateFailed("Configuration error: missing credentials")

                await self.api.login(username, password)

            # 1. Get the base list of all devices
            resp_details = await self.api.get_all_units_details()
            if not resp_details.success:
                raise UpdateFailed("Failed to fetch device list from API")

            units = resp_details.data.get("units", [])

            # Create device objects from the base details
            devices = {}
            for unit_data in units:
                device_type = unit_data.get("DeviceType", "").lower()
                device_id = unit_data.get("ID")

                if device_id is None:
                    continue

                # Only create devices for explicitly supported DeviceTypes
                if device_type == "gps":
                    try:
                        device = NorthTrackerGpsDevice(self.api, unit_data)
                        devices[device_id] = device
                    except Exception as err:
                        LOGGER.error(
                            "Failed to create GPS device for ID %s: %s", device_id, err
                        )

            # 2. Get real-time location data
            try:
                resp_realtime = await self.api.get_realtime_tracking()
                if resp_realtime.success:
                    gps_data_list = resp_realtime.data.get("gps", [])

                    for gps_data in gps_data_list:
                        device_id = gps_data.get("TrackerID")
                        if device_id is None:
                            continue

                        if device_id in devices:
                            try:
                                if devices[device_id].update_gps_data(gps_data):
                                    self._devices_with_changes.add(device_id)
                            except Exception as err:
                                LOGGER.error(
                                    "Error updating GPS data for device ID %s: %s",
                                    device_id,
                                    err,
                                )
            except Exception as err:
                LOGGER.warning("Error fetching real-time location data: %s", err)

            # Create virtual Bluetooth sensor devices
            for main_device in list(devices.values()):
                if main_device.available_bluetooth_sensors:
                    for bt_sensor in main_device.available_bluetooth_sensors:
                        try:
                            bt_device = NorthTrackerSensorDevice(main_device, bt_sensor)
                            devices[bt_device.id] = bt_device
                        except Exception as err:
                            LOGGER.error("Failed to create Bluetooth device: %s", err)

            # 3. Fetch extra details for each GPS device in parallel
            async def update_device_details(device: NorthTrackerGpsDevice) -> None:
                """Update a single device's details."""
                try:
                    if await device.async_update():
                        self._devices_with_changes.add(device.id)
                except Exception as err:
                    LOGGER.warning(
                        "Failed to update details for device %s: %s", device.name, err
                    )

            main_devices = [
                device for device in devices.values() if device.device_type == "gps"
            ]
            if main_devices:
                semaphore = asyncio.Semaphore(5)

                async def limited_update(task):
                    async with semaphore:
                        await task

                tasks = [update_device_details(device) for device in main_devices]
                await asyncio.gather(
                    *[limited_update(task) for task in tasks], return_exceptions=True
                )

            duration = (datetime.now() - start_time).total_seconds()
            LOGGER.debug("Updated %d devices in %.2fs", len(devices), duration)

            # Clear any previous error issues since update was successful
            async_delete_issue(
                self.hass, DOMAIN, f"{self.config_entry.entry_id}_api_error"
            )
            async_delete_issue(
                self.hass, DOMAIN, f"{self.config_entry.entry_id}_rate_limit"
            )

            return devices

        except AuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            async_create_issue(
                self.hass,
                DOMAIN,
                f"{self.config_entry.entry_id}_authentication_failed",
                is_fixable=False,
                is_persistent=False,
                severity=IssueSeverity.ERROR,
                translation_key="authentication_failed",
            )
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except RateLimitError as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"{self.config_entry.entry_id}_rate_limit",
                is_fixable=False,
                is_persistent=False,
                severity=IssueSeverity.WARNING,
                translation_key="rate_limit",
            )
            raise UpdateFailed(f"Rate limit exceeded: {err}") from err
        except APIError as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"{self.config_entry.entry_id}_api_error",
                is_fixable=False,
                is_persistent=False,
                severity=IssueSeverity.WARNING,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            )
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            LOGGER.exception("Unexpected error communicating with API")
            raise UpdateFailed(f"Unexpected error: {err}") from err
