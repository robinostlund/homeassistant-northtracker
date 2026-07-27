"""DataUpdateCoordinator for the NorthTracker integration."""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APIError, AuthenticationError, NorthTracker, RateLimitError
from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .devices import NorthTrackerGpsDevice, NorthTrackerSensorDevice
from .helpers import async_prime_api_timezone

type NorthTrackerConfigEntry = ConfigEntry["NorthTrackerDataUpdateCoordinator"]


class NorthTrackerDataUpdateCoordinator(
    DataUpdateCoordinator[dict[int, NorthTrackerGpsDevice]]
):
    """Class to manage fetching NorthTracker data."""

    config_entry: NorthTrackerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NorthTrackerConfigEntry) -> None:
        """Initialize."""
        self.api = NorthTracker(async_get_clientsession(hass))

        # Validate and set update interval (tunable via the options flow)
        update_interval_minutes = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL),
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

        LOGGER.debug(
            "NorthTracker coordinator initialized with a %.2f minute update interval.",
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

        # Last known real-time payload per device ID. Bluetooth sensors are only
        # discovered from this payload, so it is kept and reused when the
        # real-time endpoint fails - otherwise those devices would vanish.
        self._gps_data_cache: dict[int, dict[str, Any]] = {}

        # True when part of the last update failed. The device list may then be
        # incomplete, which makes it unsafe to remove "stale" devices.
        self.update_degraded = False

        # Whether the current real-time failure has already been logged, so an
        # outage lasting hours does not fill the log with the same warning.
        self._realtime_error_logged = False

    def device_has_changes(self, device_id: int) -> bool:
        """Check if a device has changes that require entity updates."""
        return device_id in self._devices_with_changes

    async def _async_update_data(self) -> dict[int, NorthTrackerGpsDevice]:
        """Fetch data from API endpoint."""
        start_time = time.monotonic()

        # Reset per-update state at the start of each update
        self._devices_with_changes.clear()
        self.update_degraded = False

        # Ensure the API timezone is loaded off the event loop before parsing timestamps
        await async_prime_api_timezone()

        try:
            # Authenticate only when needed (token management is handled in API class)
            if not self.api.is_authenticated:
                username = self.config_entry.data[CONF_USERNAME]
                password = self.config_entry.data[CONF_PASSWORD]
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
                    except Exception as err:  # noqa: BLE001
                        LOGGER.error(
                            "Failed to create GPS device for ID %s: %s", device_id, err
                        )

            # 2. Get real-time location data
            try:
                resp_realtime = await self.api.get_realtime_tracking()
                if not resp_realtime.success:
                    raise APIError("Real-time tracking request returned success=False")

                gps_data_by_device = {
                    gps_data["TrackerID"]: gps_data
                    for gps_data in resp_realtime.data.get("gps", [])
                    if gps_data.get("TrackerID") is not None
                }
                self._gps_data_cache = gps_data_by_device
                if self._realtime_error_logged:
                    LOGGER.info("Real-time location data is available again")
                    self._realtime_error_logged = False
            except Exception as err:  # noqa: BLE001
                # Fall back to the last known payload. Bluetooth sensor devices are
                # discovered from it, so dropping it would remove those devices and
                # their entities until the endpoint recovers.
                self.update_degraded = True
                gps_data_by_device = self._gps_data_cache
                # Only warn on the first failure; an outage can last for hours.
                log = LOGGER.debug if self._realtime_error_logged else LOGGER.warning
                log(
                    "Error fetching real-time location data, %s: %s",
                    "reusing last known data"
                    if gps_data_by_device
                    else "no cached data available",
                    err,
                )
                self._realtime_error_logged = True

            for device_id, gps_data in gps_data_by_device.items():
                device = devices.get(device_id)
                if device is None:
                    continue
                try:
                    if device.update_gps_data(gps_data):
                        self._devices_with_changes.add(device_id)
                except Exception as err:  # noqa: BLE001
                    LOGGER.error(
                        "Error updating GPS data for device ID %s: %s", device_id, err
                    )

            # Create virtual Bluetooth sensor devices
            for main_device in list(devices.values()):
                if main_device.available_bluetooth_sensors:
                    for bt_sensor in main_device.available_bluetooth_sensors:
                        try:
                            bt_device = NorthTrackerSensorDevice(main_device, bt_sensor)
                            devices[bt_device.id] = bt_device
                        except Exception as err:  # noqa: BLE001
                            LOGGER.error("Failed to create Bluetooth device: %s", err)

            # 3. Fetch extra details for each GPS device in parallel
            async def update_device_details(device: NorthTrackerGpsDevice) -> None:
                """Update a single device's details."""
                try:
                    if await device.async_update():
                        self._devices_with_changes.add(device.id)
                except Exception as err:  # noqa: BLE001
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

                # 4. Fetch geofence status once for all devices. The API returns
                # every geofence in a single call, so we filter it per device
                # rather than making one request per device.
                try:
                    resp_geofences = await self.api.get_geofences()
                    if resp_geofences.success:
                        geofences = resp_geofences.data.get("geofences", [])
                        for device in main_devices:
                            if device.update_geofence_status(geofences):
                                self._devices_with_changes.add(device.id)
                except Exception as err:  # noqa: BLE001
                    LOGGER.warning("Error fetching geofence status: %s", err)

            duration = time.monotonic() - start_time
            LOGGER.debug("Updated %d devices in %.2fs", len(devices), duration)

            # Clear any previous error issues since update was successful
            ir.async_delete_issue(
                self.hass, DOMAIN, f"{self.config_entry.entry_id}_api_error"
            )
            ir.async_delete_issue(
                self.hass, DOMAIN, f"{self.config_entry.entry_id}_rate_limit"
            )

            return devices

        except AuthenticationError as err:
            # Raising ConfigEntryAuthFailed lets the coordinator base class start the
            # reauth flow automatically; no need to trigger it manually here.
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except RateLimitError as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{self.config_entry.entry_id}_rate_limit",
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="rate_limit",
            )
            raise UpdateFailed(f"Rate limit exceeded: {err}") from err
        except APIError as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{self.config_entry.entry_id}_api_error",
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            )
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            LOGGER.exception("Unexpected error communicating with API")
            raise UpdateFailed(f"Unexpected error: {err}") from err
