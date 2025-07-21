"""North-Tracker API Client."""
from __future__ import annotations

import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Any

from .const import LOGGER


class NorthTrackerException(Exception):
    """Base exception for North-Tracker API errors."""


class AuthenticationError(NorthTrackerException):
    """Exception for authentication errors."""


class RateLimitError(NorthTrackerException):
    """Exception for rate limit errors."""


class APIError(NorthTrackerException):
    """Exception for general API errors."""

class NorthTracker:
    """North-Tracker API client with improved error handling and token management."""
    
    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the North-Tracker API client."""
        self.session = session
        self.base_url = "https://apiv2.northtracker.com/api/v1"
        self.http_headers = {
            "Content-Type": "application/json",
            "Timezone": "Europe/Stockholm",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Request-Type": "web",
        }
        self.rate_limit = 0
        self.rate_limit_remaining = 0
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._username: str | None = None
        self._password: str | None = None

    async def _update_rate_limits(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit information from response headers."""
        old_remaining = self.rate_limit_remaining
        self.rate_limit = int(response.headers.get("X-RateLimit-Limit", self.rate_limit))
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", self.rate_limit_remaining))
        
        LOGGER.debug("Rate limit info updated: %d/%d remaining (was %d)", 
                    self.rate_limit_remaining, self.rate_limit, old_remaining)
        
        # Warn if rate limit is getting low
        if self.rate_limit > 0:
            usage_percent = ((self.rate_limit - self.rate_limit_remaining) / self.rate_limit) * 100
            if usage_percent > 80:
                LOGGER.warning("Rate limit usage high: %.1f%% (%d/%d requests used)", 
                             usage_percent, self.rate_limit - self.rate_limit_remaining, self.rate_limit)

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        LOGGER.debug("Checking authentication status...")
        if not self._token:
            LOGGER.debug("No token available, need to authenticate")
        elif self._token_expires and datetime.now() >= self._token_expires:
            LOGGER.debug("Token expired at %s, need to re-authenticate", self._token_expires)
        else:
            LOGGER.debug("Token is valid until %s", self._token_expires)
            return
            
        if not self._username or not self._password:
            raise AuthenticationError("No credentials available for authentication")
        await self._login(self._username, self._password)

    async def _request(
        self, 
        method: str, 
        url: str, 
        payload: dict[str, Any] | None = None,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> NorthTrackerResponse:
        """Make an authenticated request with retry logic."""
        LOGGER.debug("Making %s request to %s (attempt %d/%d)", method, url, retry_count + 1, max_retries + 1)
        
        if payload:
            # Log payload but mask sensitive data
            safe_payload = payload.copy()
            if "password" in safe_payload:
                safe_payload["password"] = "***"
            LOGGER.debug("Request payload: %s", safe_payload)
        
        if retry_count > 0:
            wait_time = min(2 ** retry_count, 30)
            LOGGER.debug("Waiting %d seconds before retry", wait_time)
            await asyncio.sleep(wait_time)

        try:
            headers = self.http_headers.copy()
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
                LOGGER.debug("Using authentication token (preview: %s...)", self._token[:10])
            else:
                LOGGER.debug("No authentication token available")

            # Debug: Log all headers being sent (but mask authorization)
            debug_headers = headers.copy()
            if "Authorization" in debug_headers:
                debug_headers["Authorization"] = f"Bearer {self._token[:10]}..." if self._token else "None"
            LOGGER.debug("Request headers: %s", debug_headers)

            timeout = aiohttp.ClientTimeout(total=30)
            
            if method.upper() == "GET":
                async with self.session.get(url, headers=headers, timeout=timeout) as response:
                    await self._update_rate_limits(response)
                    LOGGER.debug("GET response: status=%d, content-type=%s, rate_limit=%d/%d", 
                               response.status, response.headers.get('Content-Type'), 
                               self.rate_limit_remaining, self.rate_limit)
                    
                    if response.status == 401 and retry_count == 0:
                        LOGGER.debug("Token expired (401), attempting re-authentication")
                        # Token might be expired, try to re-authenticate
                        self._token = None
                        await self._ensure_authenticated()
                        return await self._request(method, url, payload, retry_count + 1, max_retries)
                    
                    if response.status == 429:
                        if retry_count < max_retries:
                            wait_time = 2 ** (retry_count + 1)
                            LOGGER.warning("Rate limit exceeded, retrying in %d seconds", wait_time)
                            return await self._request(method, url, payload, retry_count + 1, max_retries)
                        raise RateLimitError("Rate limit exceeded")
                    
                    response.raise_for_status()
                    response_data = await response.json()
                    LOGGER.debug("GET response data keys: %s", list(response_data.keys()) if isinstance(response_data, dict) else "non-dict")
                    return NorthTrackerResponse(response_data)
            else:
                async with self.session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                    await self._update_rate_limits(response)
                    LOGGER.debug("POST response: status=%d, content-type=%s, rate_limit=%d/%d", 
                               response.status, response.headers.get('Content-Type'),
                               self.rate_limit_remaining, self.rate_limit)
                    
                    if response.status == 401 and retry_count == 0:
                        LOGGER.debug("Token expired (401), attempting re-authentication")
                        # Token might be expired, try to re-authenticate
                        self._token = None
                        await self._ensure_authenticated()
                        return await self._request(method, url, payload, retry_count + 1, max_retries)
                    
                    if response.status == 429:
                        if retry_count < max_retries:
                            wait_time = 2 ** (retry_count + 1)
                            LOGGER.warning("Rate limit exceeded, retrying in %d seconds", wait_time)
                            return await self._request(method, url, payload, retry_count + 1, max_retries)
                        raise RateLimitError("Rate limit exceeded")
                    
                    response.raise_for_status()
                    response_data = await response.json()
                    LOGGER.debug("POST response data keys: %s", list(response_data.keys()) if isinstance(response_data, dict) else "non-dict")
                    return NorthTrackerResponse(response_data)

        except asyncio.TimeoutError as err:
            LOGGER.debug("Request timeout after 30 seconds")
            if retry_count < max_retries:
                LOGGER.warning("Request timeout, retrying (%d/%d)", retry_count + 1, max_retries)
                return await self._request(method, url, payload, retry_count + 1, max_retries)
            raise APIError(f"Request timeout after {max_retries} retries") from err
        except aiohttp.ClientError as err:
            LOGGER.debug("Client error: %s", err)
            if retry_count < max_retries:
                LOGGER.warning("Client error, retrying (%d/%d): %s", retry_count + 1, max_retries, err)
                return await self._request(method, url, payload, retry_count + 1, max_retries)
            raise APIError(f"Client error after {max_retries} retries: {err}") from err

    async def _get_data(self, url: str) -> NorthTrackerResponse:
        """Make a GET request."""
        await self._ensure_authenticated()
        return await self._request("GET", url)

    async def _post_data(self, url: str, payload: dict[str, Any] | None = None) -> NorthTrackerResponse:
        """Make a POST request."""
        await self._ensure_authenticated()
        return await self._request("POST", url, payload)

    async def _login(self, username: str, password: str) -> None:
        """Internal login method that sets the token."""
        LOGGER.debug("Attempting to login with username: %s", username)
        url = f"{self.base_url}/login"
        payload = {"username": username, "password": password, "remember_me": False, "subsiteid": 0}
        
        try:
            # Make login request without authentication (bypass _get_data/_post_data)
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.post(url, json=payload, headers=self.http_headers, timeout=timeout) as response:
                await self._update_rate_limits(response)
                LOGGER.debug("Login response: status=%d, content-type=%s", 
                           response.status, response.headers.get('Content-Type'))
                
                response.raise_for_status()
                response_data = await response.json()
                resp = NorthTrackerResponse(response_data)
                
                if resp.success:
                    self._token = resp.data.get('user', {}).get('token', '')
                    # Set token expiration to 23 hours from now (assuming 24h validity)
                    self._token_expires = datetime.now() + timedelta(hours=23)
                    LOGGER.debug("Successfully authenticated, token expires at %s", self._token_expires)
                    LOGGER.debug("Token preview: %s...", self._token[:10] if self._token else "empty")
                else:
                    LOGGER.error("Login failed: API returned success=False")
                    raise AuthenticationError("Login failed: Invalid response from server")
                    
        except aiohttp.ClientError as err:
            LOGGER.error("Login failed with client error: %s", err)
            raise AuthenticationError(f"Login failed: {err}") from err
        except Exception as err:
            LOGGER.error("Login failed with error: %s", err)
            if isinstance(err, AuthenticationError):
                raise
            raise AuthenticationError(f"Login failed: {err}") from err

    async def login(self, username: str, password: str) -> bool:
        """Authenticate with the North-Tracker API and store credentials for future use."""
        self._username = username
        self._password = password
        await self._login(username, password)
        return True
    
    async def logout(self) -> None:
        """Logout from the North-Tracker API."""
        url = f"{self.base_url}/user/logout"
        try:
            await self._post_data(url)
        finally:
            # Clear credentials regardless of logout success
            self._token = None
            self._token_expires = None
    
    async def get_tracking_details(self) -> NorthTrackerResponse:
        """Get tracking details from the API."""
        url = f"{self.base_url}/user/realtimetracking/get"
        return await self._get_data(url)

    async def get_all_units_details(self) -> NorthTrackerResponse:
        """Get details for all units."""
        LOGGER.debug("Fetching all units details from API")
        url = f"{self.base_url}/user/terminal/get-all-units-details"
        response = await self._get_data(url)
        if response.success:
            units_count = len(response.data.get("units", []))
            LOGGER.debug("Successfully fetched details for %d units", units_count)
        else:
            LOGGER.warning("Failed to fetch all units details")
        return response

    async def get_realtime_tracking(self) -> NorthTrackerResponse:
        """Fetch real-time location data for all devices."""
        LOGGER.debug("Fetching real-time tracking data from API")
        url = f"{self.base_url}/user/realtimetracking/get?lang=en"
        response = await self._get_data(url)
        if response.success:
            gps_count = len(response.data.get("gps", []))
            LOGGER.debug("Successfully fetched GPS data for %d devices", gps_count)
        else:
            LOGGER.warning("Failed to fetch real-time tracking data")
        return response

    async def get_unit_details(self, device_id: int, device_type: str) -> NorthTrackerResponse:
        """Get detailed information for a specific unit."""
        LOGGER.debug("Fetching detailed info for device %d (type: %s)", device_id, device_type)
        url = f"{self.base_url}/user/terminal/edit-terminal"
        response = await self._post_data(url, {"device_id": device_id, "device_type": device_type})
        if response.success:
            LOGGER.debug("Successfully fetched detailed info for device %d", device_id)
        else:
            LOGGER.warning("Failed to fetch detailed info for device %d", device_id)
        return response

    async def get_unit_features(self, device_imei: str) -> NorthTrackerResponse:
        """Get unit features by IMEI."""
        url = f"{self.base_url}/user/terminal/get-unit-features"
        return await self._post_data(url, {"Imei": device_imei})

    async def get_unit_lock_status(self, device_id: int) -> NorthTrackerResponse:
        """Get unit lock status by device ID."""
        LOGGER.debug("Fetching lock status for device ID %d", device_id)
        url = f"{self.base_url}/user/terminal/access/lockstatus"
        response = await self._post_data(url, {"terminal_id": device_id})
        if response.success:
            LOGGER.debug("Successfully fetched lock status for device ID %d", device_id)
        else:
            LOGGER.warning("Failed to fetch lock status for device ID %d", device_id)
        return response

    async def update_unit_features(self, device_imei: str, features_data: dict) -> NorthTrackerResponse:
        """Update unit features/settings."""
        LOGGER.debug("Updating unit features for device IMEI %s", device_imei)
        url = f"{self.base_url}/user/terminal/enable-features"
        
        # Ensure the payload has the correct structure
        payload = {
            "Imeis": [device_imei],
            "Settings": features_data
        }
        
        # Debug: Log the payload structure (without sensitive data)
        settings_keys = list(features_data.keys())[:10] if isinstance(features_data, dict) else "Not a dict"
        LOGGER.debug("Sending payload to enable-features API - Imeis: %s, Settings keys: %s (total: %d)", 
                    payload["Imeis"], settings_keys, len(features_data) if isinstance(features_data, dict) else 0)
        
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully updated unit features for device IMEI %s", device_imei)
        else:
            LOGGER.warning("Failed to update unit features for device IMEI %s", device_imei)
        return response

    async def set_low_battery_alert(self, device_imei: str, enabled: bool, threshold: float = 12.1) -> NorthTrackerResponse:
        """Enable/disable low battery alert and set threshold."""
        LOGGER.debug("Setting low battery alert for device IMEI %s: enabled=%s, threshold=%.1f", 
                    device_imei, enabled, threshold)
        
        # Use the generic settings update method
        settings_updates = {
            "LowBatteryAlertEnabled": 1 if enabled else 0,  # Convert boolean to 1/0 as API expects
            "LowBatteryThreshold": str(threshold),  # Convert to string as shown in example
            "SendLowBatteryCommand": True
        }
        
        return await self.update_unit_features_settings(device_imei, settings_updates)

    async def update_unit_features_settings(self, device_imei: str, settings_updates: dict) -> NorthTrackerResponse:
        """Update device settings with a generic, reusable payload structure.
        
        Args:
            device_imei: Device IMEI
            settings_updates: Dictionary of settings to update (e.g. {"LowBatteryAlertEnabled": True})
        """
        LOGGER.debug("Updating generic settings for device IMEI %s: %s", device_imei, settings_updates)
        
        # Create the base settings structure that the API expects
        base_settings = {
            "ID": "",
            "ProfileName": "",
            "ProfileDescription": "",
            "TripType": "",
            "TripTypeSettings": {
                "default_trip": 0,
                "private_trip": 0,
                "onmap_during_workinghour": 0,
                "businessTripDays": ""
            },
            "CarBenefitSettings": {
                "benefit_type": "",
                "fuel_consumption_company": "",
                "vehicle_type": "",
                "currency": "",
                "fuel_consumption_private": ""
            },
            "CarBenefitEnabled": False,
            "GreenDrivingSensitivity": "",
            "OverspeedingThreshold": "",
            "SaveConfiguration": False,
            "GreenDrivingEnabled": False,
            "OverSpeedingEnabled": False,
            "WorkingHoursEnabled": False,
            "FromApp": "false",
            "SaveCarBenefit": False,
            "SaveWorkingHours": False,
            "SendEcoDrivingCommand": False,
            "SendOverspeedingCommand": False,
            "IsKorjournalUnit": False
        }
        
        # Apply the specific updates
        final_settings = {**base_settings, **settings_updates}
        
        LOGGER.debug("Sending generic settings update with %d base fields + %d custom fields", 
                    len(base_settings), len(settings_updates))
        
        return await self.update_unit_features(device_imei, final_settings)

    async def output_turn_on(self, device_id: int, output_number: int) -> NorthTrackerResponse:
        """Turn on a digital output."""
        LOGGER.debug("Turning on output %d for device ID %d", output_number, device_id)
        url = f"{self.base_url}/user/terminal/relaysetting/sendmsg"
        payload = {
            "terminal_id": device_id,
            "doutnumber": output_number,
            "doutvalue": 1
        }
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully sent turn ON command for output %d, device ID %d", output_number, device_id)
        else:
            LOGGER.warning("Failed to turn on output %d for device ID %d", output_number, device_id)
        return response

    async def output_turn_off(self, device_id: int, output_number: int) -> NorthTrackerResponse:
        """Turn off a digital output."""
        LOGGER.debug("Turning off output %d for device ID %d", output_number, device_id)
        url = f"{self.base_url}/user/terminal/relaysetting/sendmsg"
        payload = {
            "terminal_id": device_id,
            "doutnumber": output_number,
            "doutvalue": 0
        }
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully sent turn OFF command for output %d, device ID %d", output_number, device_id)
        else:
            LOGGER.warning("Failed to turn off output %d for device ID %d", output_number, device_id)
        return response

    async def input_turn_on(self, device_id: int, input_number: int) -> NorthTrackerResponse:
        """Enable alert for a digital input."""
        LOGGER.debug("Enabling alert for input %d on device ID %d", input_number, device_id)
        # Note: This might use a different endpoint than outputs - may need adjustment
        url = f"{self.base_url}/user/terminal/dinsetting/sendmsg"
        payload = {
            "terminal_id": device_id,
            "dinnumber": input_number,
            "dinvalue": 1
        }
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully enabled alert for input %d, device ID %d", input_number, device_id)
        else:
            LOGGER.warning("Failed to enable alert for input %d on device ID %d", input_number, device_id)
        return response

    async def input_turn_off(self, device_id: int, input_number: int) -> NorthTrackerResponse:
        """Disable alert for a digital input."""
        LOGGER.debug("Disabling alert for input %d on device ID %d", input_number, device_id)
        # Note: This might use a different endpoint than outputs - may need adjustment
        url = f"{self.base_url}/user/terminal/dinsetting/sendmsg"
        payload = {
            "terminal_id": device_id,
            "dinnumber": input_number,
            "dinvalue": 0
        }
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully disabled alert for input %d, device ID %d", input_number, device_id)
        else:
            LOGGER.warning("Failed to disable alert for input %d on device ID %d", input_number, device_id)
        return response

    async def output_check_ack(self, ack_id: int) -> NorthTrackerResponse:
        """Check acknowledgment for output command."""
        LOGGER.debug("Checking acknowledgment for ID %d", ack_id)
        url = f"{self.base_url}/user/terminal/relaysetting/check-ack"
        payload = {
            "id": ack_id
        }
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully checked acknowledgment for ID %d", ack_id)
        else:
            LOGGER.warning("Failed to check acknowledgment for ID %d", ack_id)
        return response


class NorthTrackerResponse:
    """Wrapper for API responses from North-Tracker."""
    
    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize the response wrapper."""
        self.response_data = data

    @property
    def success(self) -> bool:
        """Return whether the API call was successful."""
        return self.response_data.get("success", False)

    @property
    def data(self) -> Any:
        """Return the data portion of the response."""
        return self.response_data.get("data", {})


class NorthTrackerDevice:
    """Represents a North-Tracker device with all its data and capabilities."""
    
    def __init__(self, tracker: NorthTracker, device_data: dict[str, Any]) -> None:
        """Initialize a device instance."""
        self.tracker = tracker
        self._device_data = device_data
        self._device_data_extra: dict[str, Any] = {}
        self._device_lock_data: dict[str, Any] = {}
        self._device_gps_data: dict[str, Any] = {}
        self._device_features_data: dict[str, Any] = {}
        self._last_update: datetime | None = None
        
        # Dynamically discover digital inputs and outputs
        self._available_inputs = self._discover_digital_inputs()
        self._available_outputs = self._discover_digital_outputs()
        
        # Dynamically discover Bluetooth sensors
        self._available_bluetooth_sensors = self._discover_bluetooth_sensors()
        
        LOGGER.debug("Device %s discovered capabilities: %d inputs, %d outputs, %d bluetooth sensors", 
                    self.name, len(self._available_inputs), len(self._available_outputs),
                    len(self._available_bluetooth_sensors))

    async def async_update(self) -> bool:
        """Update device with latest information from the API.
        
        Returns True if device data has actually changed, False otherwise.
        """
        LOGGER.debug("Updating device %s (ID: %s)", self.name, self.id)
        data_changed = False
        
        try:
            # Get detailed device information
            LOGGER.debug("Fetching device details for %s", self.name)
            resp_details = await self.tracker.get_unit_details(self.id, self.device_type)
            if resp_details.success:
                # Check if device data has changed
                if self._device_data_extra != resp_details.data:
                    LOGGER.debug("Device details changed for %s", self.name)
                    self._device_data_extra = resp_details.data
                    data_changed = True
                else:
                    LOGGER.debug("Device details unchanged for %s", self.name)
            else:
                LOGGER.warning("Failed to fetch device details for %s", self.name)

            # Get lock status
            LOGGER.debug("Fetching lock status for %s", self.name)
            resp_lock = await self.tracker.get_unit_lock_status(self.id)
            if resp_lock.success:
                # Check if lock data has changed
                if self._device_lock_data != resp_lock.data:
                    LOGGER.debug("Lock status changed for %s", self.name)
                    self._device_lock_data = resp_lock.data
                    data_changed = True
                else:
                    LOGGER.debug("Lock status unchanged for %s", self.name)
            else:
                LOGGER.warning("Failed to fetch lock status for %s", self.name)

            # Get unit features (for battery alert settings etc.)
            LOGGER.debug("Fetching unit features for %s", self.name)
            resp_features = await self.tracker.get_unit_features(self.imei)
            if resp_features.success:
                features_data = resp_features.data
                if features_data and len(features_data) > 0:
                    # Check if features data has changed
                    if self._device_features_data != features_data[0]:
                        LOGGER.debug("Unit features changed for %s", self.name)
                        self._device_features_data = features_data[0]
                        data_changed = True
                    else:
                        LOGGER.debug("Unit features unchanged for %s", self.name)
                else:
                    LOGGER.debug("No features data found for %s", self.name)
            else:
                LOGGER.warning("Failed to fetch unit features for %s", self.name)
                
            self._last_update = datetime.now()
            if data_changed:
                LOGGER.debug("Device %s data changed, update completed at %s", self.name, self._last_update)
            else:
                LOGGER.debug("Device %s data unchanged, update completed at %s", self.name, self._last_update)
            
            return data_changed
            
        except Exception as err:
            LOGGER.error("Error updating device %s: %s", self.name, err)
            raise

    def update_gps_data(self, gps_data: dict[str, Any]) -> bool:
        """Update the device with real-time location data.
        
        Returns True if the GPS data has actually changed, False otherwise.
        """
        # Compare with previous GPS data to detect changes
        if self._device_gps_data == gps_data:
            LOGGER.debug("GPS data unchanged for device %s", self.name)
            return False
            
        LOGGER.debug("GPS data changed for device %s: has_position=%s, lat=%s, lon=%s", 
                    self.name, gps_data.get("HasPosition"), 
                    gps_data.get("Latitude"), gps_data.get("Longitude"))
        self._device_gps_data = gps_data
        
        # Re-discover Bluetooth sensors when GPS data changes (as PairedSensors come with GPS data)
        self._available_bluetooth_sensors = self._discover_bluetooth_sensors()
        
        return True

    def _discover_digital_inputs(self) -> list[int]:
        """Discover available digital inputs based on device data."""
        inputs = []
        # Check for digital input status fields in the device data
        for key, value in self._device_data.items():
            if key.startswith("Din") and key.endswith("Status"):
                try:
                    # Extract input number from key like "Din2Status", "Din3Status", etc.
                    input_num = int(key[3:-6])  # Remove "Din" prefix and "Status" suffix
                    inputs.append(input_num)
                    LOGGER.debug("Found digital input %d for device %s (status: %s)", 
                               input_num, self.name, value)
                except ValueError:
                    LOGGER.warning("Could not parse input number from key: %s", key)
        
        return sorted(inputs)
    
    def _discover_digital_outputs(self) -> list[int]:
        """Discover available digital outputs based on device data."""
        outputs = []
        # Check for digital output status fields in the device data
        for key, value in self._device_data.items():
            if key.startswith("Dout") and key.endswith("Status"):
                try:
                    # Extract output number from key like "Dout1Status", "Dout2Status", etc.
                    output_num = int(key[4:-6])  # Remove "Dout" prefix and "Status" suffix
                    outputs.append(output_num)
                    LOGGER.debug("Found digital output %d for device %s (status: %s)", 
                               output_num, self.name, value)
                except ValueError:
                    LOGGER.warning("Could not parse output number from key: %s", key)
        
        return sorted(outputs)

    def _discover_bluetooth_sensors(self) -> list[dict[str, Any]]:
        """Discover available Bluetooth sensors based on GPS data."""
        sensors = []
        # Check for PairedSensors in GPS data
        paired_sensors = self._device_gps_data.get("PairedSensors", [])
        
        for sensor in paired_sensors:
            if isinstance(sensor, dict):
                serial_number = sensor.get("SerialNumber")
                bluetooth_info = sensor.get("bluetooth_info", {})
                latest_data = sensor.get("latest_sensor_data", {})
                
                if serial_number and bluetooth_info:
                    sensor_config = {
                        "serial_number": serial_number,
                        "name": bluetooth_info.get("Name", f"Bluetooth Sensor {serial_number}"),
                        "enable_temperature": bool(bluetooth_info.get("EnableTemperature", 0)),
                        "enable_humidity": bool(bluetooth_info.get("EnableHumidity", 0)),
                        "enable_door_sensor": bool(bluetooth_info.get("EnableDoorSensor", 0)),
                        "has_data": bool(latest_data),
                        "latest_sensor_data": latest_data  # Include the actual sensor data
                    }
                    sensors.append(sensor_config)
                    LOGGER.debug("Found Bluetooth sensor %s (%s) for device %s - temp:%s, humidity:%s, door:%s", 
                               serial_number, sensor_config["name"], self.name,
                               sensor_config["enable_temperature"], sensor_config["enable_humidity"],
                               sensor_config["enable_door_sensor"])
        
        return sensors

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        # Consider device available if we have basic data
        return bool(self._device_data.get("ID"))

    @property
    def available_inputs(self) -> list[int]:
        """Return list of available digital input numbers."""
        return self._available_inputs

    @property
    def available_outputs(self) -> list[int]:
        """Return list of available digital output numbers."""
        return self._available_outputs

    @property
    def available_bluetooth_sensors(self) -> list[dict[str, Any]]:
        """Return list of available Bluetooth sensors."""
        return self._available_bluetooth_sensors

    @property
    def id(self) -> int | str:
        """Return the device ID."""
        device_id = self._device_data.get("ID", 0)
        # Some devices may have string IDs like "1250b"
        return device_id
    
    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device_data.get("NameOnly", "Unknown Device")

    @property
    def imei(self) -> str:
        """Return the device IMEI."""
        return self._device_data.get("Imei", "")

    @property
    def device_type(self) -> str:
        """Return the device type."""
        return self._device_data.get("DeviceType", "gps")

    @property
    def model(self) -> str:
        """Return the device model."""
        return self._device_data.get("GpsModel", "")

    @property
    def registration_number(self) -> str | None:
        """Return the vehicle registration number."""
        return self._device_data.get("RegNr")

    @property
    def latitude(self) -> float | None:
        """Return current latitude."""
        lat = self._device_gps_data.get("Latitude")
        if lat is None:
            return None
        try:
            return float(lat)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid latitude value: %s", lat)
            return None

    @property
    def longitude(self) -> float | None:
        """Return current longitude."""
        lon = self._device_gps_data.get("Longitude")
        if lon is None:
            return None
        try:
            return float(lon)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid longitude value: %s", lon)
            return None

    @property
    def has_position(self) -> bool:
        """Return True if device has GPS position data."""
        return bool(self._device_gps_data.get("HasPosition", False))

    @property
    def gps_accuracy(self) -> int:
        """Return GPS accuracy level (0-5)."""
        accuracy = self._device_gps_data.get("GPSAccuracy", 0)
        try:
            return int(accuracy)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid GPS accuracy value: %s", accuracy)
            return 0

    @property
    def bluetooth_enabled(self) -> bool:
        """Return True if Bluetooth is enabled on the device."""
        bluetooth_enabled = self._device_data_extra.get("terminal",{}).get("BluetoothStatus", False)
        return bool(bluetooth_enabled)

    @property
    def gps_signal(self) -> int | None:
        """Return GPS signal strength as percentage (0-100%)."""
        # Use GPSAccuracy from GPS data (0-5 scale) and convert to percentage
        accuracy = self._device_gps_data.get("GPSAccuracy")
        if accuracy is None:
            return None
        try:
            # Convert 0-5 scale to 0-100% (5 = best signal = 100%)
            accuracy_int = int(accuracy)
            if accuracy_int < 0:
                return 0
            elif accuracy_int > 5:
                return 100
            else:
                return int((accuracy_int / 5) * 100)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid GPS signal value: %s", accuracy)
            return None

    @property
    def last_seen(self) -> datetime | None:
        """Return the last seen timestamp."""
        last_seen_str = self._device_data.get("LastSeen")
        if not last_seen_str:
            return None
        
        try:
            # Parse the timestamp (assuming format like "2025-07-18 22:05:52")
            return datetime.fromisoformat(last_seen_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid last seen timestamp: %s", last_seen_str)
            return None

    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage."""
        battery_str = self._device_data.get("BatteryVoltage")
        if battery_str is None:
            return None
        
        try:
            # Handle different formats that might be returned
            if isinstance(battery_str, (int, float)):
                # If it's already a number, convert from millivolts to volts
                return float(battery_str) / 1000.0
            elif isinstance(battery_str, str):
                # Remove any non-numeric characters and convert from millivolts to volts
                clean_str = ''.join(c for c in battery_str if c.isdigit() or c == '.')
                if clean_str:
                    voltage_mv = float(clean_str)
                    return voltage_mv / 1000.0
            return None
        except (ValueError, TypeError):
            LOGGER.warning("Invalid battery voltage format: %s", battery_str)
            return None

    @property
    def odometer(self) -> float | None:
        """Return odometer reading in kilometers."""
        odometer = self._device_data.get("Odometer")
        if odometer is None:
            return None
        try:
            return float(odometer)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid odometer value: %s", odometer)
            return None

    @property
    def report_frequency(self) -> int | None:
        """Return report frequency in seconds."""
        frequency = self._device_gps_data.get("ReportFrequency")
        if frequency is None:
            return None
        try:
            return int(frequency)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid report frequency value: %s", frequency)
            return None

    @property
    def network_signal(self) -> int | None:
        """Return network signal strength as percentage (0-100%)."""
        # Use NetworkQuality from GPS data (0-5 scale) and convert to percentage
        signal = self._device_gps_data.get("NetworkQuality")
        if signal is None:
            return None
        try:
            # Convert 0-5 scale to 0-100% (5 = best signal = 100%)
            signal_int = int(signal)
            if signal_int < 0:
                return 0
            elif signal_int > 5:
                return 100
            else:
                return int((signal_int / 5) * 100)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid network signal value: %s", signal)
            return None

    @property
    def speed(self) -> int:
        """Return current speed in km/h."""
        speed = self._device_gps_data.get("Speed", 0)
        try:
            return int(speed)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid speed value: %s", speed)
            return 0
    
    @property
    def course(self) -> int:
        """Return course/heading of the device in degrees."""
        course = self._device_gps_data.get("Azimuth", 0)
        try:
            # Handle both int and float values
            if isinstance(course, (int, float)):
                course_int = int(float(course))  # Convert via float first to handle string floats
                # Validate course range (0-359 degrees)
                if 0 <= course_int <= 359:
                    return course_int
                LOGGER.warning("Course value out of range: %s", course_int)
                return 0
            else:
                # Try to convert string to float first, then to int
                course_float = float(course)
                course_int = int(course_float)
                # Validate course range (0-359 degrees)
                if 0 <= course_int <= 359:
                    return course_int
                LOGGER.warning("Course value out of range: %s", course_int)
                return 0
        except (ValueError, TypeError) as e:
            LOGGER.warning("Invalid course value: %s (error: %s)", course, e)
            return 0
    
    @property
    def low_battery_alert_enabled(self) -> bool:
        """Return whether low battery alert is enabled."""
        return self._device_features_data.get("LowBatteryAlertEnabled", False)
    
    @property
    def low_battery_threshold(self) -> float | None:
        """Return low battery alert threshold in volts."""
        threshold = self._device_features_data.get("LowBatteryThreshold")
        if threshold is None:
            return None
        try:
            return float(threshold)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid low battery threshold value: %s", threshold)
            return None

    @property
    def subscription_type(self) -> str:
        """Return the device subscription type."""
        return self._device_data.get("SubscriptionType", "")

    @property
    def operating_time(self) -> str:
        """Return the device operating time."""
        return self._device_data.get("OperatingTime", "")

    @property
    def lock_status(self) -> bool:
        """Return whether the device is locked."""
        return bool(self._device_lock_data.get("lockedstatus", False))

    @property
    def locked_by(self) -> str:
        """Return who locked the device."""
        return self._device_lock_data.get("lockedBy", "")

    @property
    def sos_alarm_enabled(self) -> bool:
        """Return whether SOS alarm is enabled."""
        return bool(self._device_data_extra.get("SoSAlarmEnabled", False))

    # Digital input/output methods
    def get_digital_input_state(self, input_number: int) -> bool | None:
        """Get the state of a digital input."""
        key = f"Din{input_number}Status"
        status = self._device_data.get(key)
        if status is None:
            return None
        return status.lower() == "on" if isinstance(status, str) else bool(status)

    def get_digital_output_state(self, output_number: int) -> bool | None:
        """Get the state of a digital output.""" 
        key = f"Dout{output_number}Status"
        status = self._device_data.get(key)
        if status is None:
            return None
        return status.lower() == "on" if isinstance(status, str) else bool(status)

    def get_output_status(self, output_number: int) -> bool:
        """Get the status of a digital output (used by switch entities)."""
        state = self.get_digital_output_state(output_number)
        return state if state is not None else False

    def get_input_status(self, input_number: int) -> bool:
        """Get the status of a digital input (used by switch entities)."""
        state = self.get_digital_input_state(input_number)
        return state if state is not None else False


class NorthTrackerBluetoothDevice:
    """Represents a virtual Bluetooth sensor device connected to a main GPS tracker."""
    
    def __init__(self, parent_device: NorthTrackerDevice, bt_sensor_data: dict[str, Any]) -> None:
        """Initialize a Bluetooth sensor device instance."""
        self.parent_device = parent_device
        self.tracker = parent_device.tracker
        self._bt_sensor_data = bt_sensor_data
        self._serial_number = bt_sensor_data["serial_number"]
        self._sensor_name = bt_sensor_data["name"]
        
        LOGGER.debug("Created Bluetooth device for sensor: %s (%s)", self._sensor_name, self._serial_number)

    @property
    def id(self) -> str:
        """Return a unique device ID for this Bluetooth sensor."""
        # Use parent ID + serial number to create unique ID
        return f"{self.parent_device.id}_bt_{self._serial_number}"
    
    @property
    def name(self) -> str:
        """Return the Bluetooth sensor name."""
        return self._sensor_name
    
    @property
    def device_type(self) -> str:
        """Return the device type."""
        return "bluetooth_sensor"
    
    @property
    def model(self) -> str:
        """Return the device model."""
        return "Bluetooth Sensor"
    
    @property
    def imei(self) -> str:
        """Return the serial number as IMEI equivalent."""
        return self._serial_number
    
    @property
    def available(self) -> bool:
        """Return True if Bluetooth sensor has data."""
        return self._bt_sensor_data.get("has_data", False)
    
    @property
    def serial_number(self) -> str:
        """Return the Bluetooth sensor serial number."""
        return self._serial_number
    
    @property
    def sensor_data(self) -> dict[str, Any]:
        """Return the Bluetooth sensor data."""
        return self._bt_sensor_data
    
    # Bluetooth sensor properties - direct access to sensor data
    @property
    def temperature(self) -> float | None:
        """Return temperature reading from this Bluetooth sensor."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                temp_str = sensor.get("latest_sensor_data", {}).get("Temperature")
                if temp_str is None:
                    return None
                try:
                    return float(temp_str)
                except (ValueError, TypeError):
                    LOGGER.warning("Invalid temperature value for sensor %s: %s", self._serial_number, temp_str)
                    return None
        return None

    @property
    def humidity(self) -> int | None:
        """Return humidity reading from this Bluetooth sensor."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                humidity_str = sensor.get("latest_sensor_data", {}).get("Humidity")
                if humidity_str is None:
                    return None
                try:
                    return int(humidity_str)
                except (ValueError, TypeError):
                    LOGGER.warning("Invalid humidity value for sensor %s: %s", self._serial_number, humidity_str)
                    return None
        return None

    @property
    def battery_percentage(self) -> int | None:
        """Return battery percentage from this Bluetooth sensor."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                battery_str = sensor.get("latest_sensor_data", {}).get("BatteryPercentage")
                if battery_str is None:
                    return None
                try:
                    return int(battery_str)
                except (ValueError, TypeError):
                    LOGGER.warning("Invalid battery percentage value for sensor %s: %s", self._serial_number, battery_str)
                    return None
        return None

    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage from this Bluetooth sensor."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                voltage_str = sensor.get("latest_sensor_data", {}).get("BatteryVoltage")
                if voltage_str is None:
                    return None
                try:
                    # Convert from millivolts to volts
                    voltage_mv = float(voltage_str)
                    return voltage_mv / 1000.0
                except (ValueError, TypeError):
                    LOGGER.warning("Invalid battery voltage value for sensor %s: %s", self._serial_number, voltage_str)
                    return None
        return None

    @property
    def magnetic_contact(self) -> bool | None:
        """Return magnetic contact state from this Bluetooth sensor."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                magnetic_state = sensor.get("latest_sensor_data", {}).get("MagneticField")
                if magnetic_state is None:
                    return None
                return bool(magnetic_state)
        return None

    @property
    def last_seen(self) -> datetime | None:
        """Return last seen timestamp for this Bluetooth sensor."""
        for sensor in self.parent_device._available_bluetooth_sensors:
            if sensor["serial_number"] == self._serial_number:
                send_time_str = sensor.get("latest_sensor_data", {}).get("Send_Time")
                if not send_time_str:
                    return None
                try:
                    # Parse the timestamp (assuming format like "2025-07-19 10:55:08")
                    return datetime.fromisoformat(send_time_str).replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    LOGGER.warning("Invalid Bluetooth sensor last seen timestamp for %s: %s", self._serial_number, send_time_str)
                    return None
        return None
    
    async def async_update(self) -> bool:
        """Update is handled by parent device. Always return False (no direct changes)."""
        # The parent device handles all updates for Bluetooth sensors
        return False

    # def update_gps_data(self, gps_data: dict[str, Any]) -> bool:
    #     """Bluetooth sensors don't have GPS data. Always return False."""
    #     return False
