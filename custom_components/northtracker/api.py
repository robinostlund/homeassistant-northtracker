"""North-Tracker API Client."""
from __future__ import annotations

import asyncio
import aiohttp
from datetime import datetime, timedelta
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
        
        LOGGER.debug("Device %s discovered capabilities: %d inputs, %d outputs", 
                    self.name, len(self._available_inputs), len(self._available_outputs))

    async def async_update(self) -> bool:
        """Update device with latest information from the API.
        
        Returns True if device data has actually changed, False otherwise.
        """
        LOGGER.debug("Updating device %s (ID: %d)", self.name, self.id)
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
    def id(self) -> int:
        """Return the device ID."""
        return self._device_data.get("ID", 0)
    
    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device_data.get("NameOnly", "")

    @property
    def device_type(self) -> str:
        """Return the device type."""
        return self._device_data.get("DeviceType", "")

    @property
    def imei(self) -> str:
        """Return the device IMEI."""
        return self._device_data.get("Imei", "")

    @property
    def model(self) -> str:
        """Return the device model."""
        return self._device_data.get("GpsModel", "")

    @property
    def bluetooth_enabled(self) -> bool:
        """Return whether Bluetooth is enabled."""
        ble_enabled = self._device_data.get("BleEnabled", 0)
        return bool(ble_enabled)

    @property
    def gps_signal(self) -> int | None:
        """Return GPS signal strength as percentage."""
        gps_value = self._device_data.get("GPS")
        if gps_value is None:
            return None
        try:
            return int(gps_value)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid GPS signal value: %s", gps_value)
            return None

    @property
    def last_seen(self) -> datetime | None:
        """Return the last seen timestamp."""
        last_seen_str = self._device_data.get("LastSeen")
        if not last_seen_str:
            return None
        
        try:
            # Parse the timestamp string and make it timezone-aware
            from datetime import datetime
            import pytz
            
            # Parse the datetime string (assuming format: "2025-07-18 08:57:28")
            dt = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
            
            # Make it timezone-aware (assuming UTC, adjust if needed)
            dt_utc = pytz.UTC.localize(dt)
            return dt_utc
            
        except (ValueError, TypeError) as e:
            LOGGER.warning("Invalid last_seen timestamp value: %s, error: %s", last_seen_str, e)
            return None

    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage in volts."""
        voltage = self._device_data.get("BatteryVoltage")
        if voltage is not None:
            try:
                # Convert from millivolts to volts (12420 -> 12.42)
                voltage_mv = float(voltage)
                return voltage_mv / 1000.0
            except (ValueError, TypeError):
                LOGGER.warning("Invalid battery voltage value: %s", voltage)
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
    def alarm_status(self) -> bool:
        """Return alarm status."""
        return self._device_lock_data.get("lockedstatus", False)

    @property
    def lock_status(self) -> bool:
        """Return lock status."""
        return self._device_lock_data.get("lockedstatus", False)
    
    @property
    def report_frequency(self) -> int | None:
        """Return report frequency in seconds."""
        try:
            terminal_data = self._device_data_extra.get("terminal", {})
            frequency = terminal_data.get("ReportFrequency")
            if frequency is None:
                return None
            return int(frequency)
        except (ValueError, TypeError, AttributeError):
            LOGGER.warning("Invalid report frequency value")
            return None
    
    def get_input_status(self, input_number: int) -> bool:
        """Return the state of a specific digital input."""
        if input_number not in self._available_inputs:
            LOGGER.warning("Input %d not available on device %s", input_number, self.name)
            return False
        
        key = f"Din{input_number}Status"
        status = self._device_data.get(key, "Off")
        return status == "On"
    
    def get_output_status(self, output_number: int) -> bool:
        """Return the state of a specific digital output."""
        if output_number not in self._available_outputs:
            LOGGER.warning("Output %d not available on device %s", output_number, self.name)
            return False
        
        key = f"Dout{output_number}Status"
        status = self._device_data.get(key, "Off")
        return status == "On"
    
    @property
    def has_position(self) -> bool:
        """Return true if the device has a valid GPS position."""
        return self._device_gps_data.get("HasPosition", False)

    @property
    def latitude(self) -> float | None:
        """Return latitude of the device."""
        if not self.has_position:
            return None
        lat = self._device_gps_data.get("Latitude")
        if lat is not None:
            try:
                lat_float = float(lat)
                # Validate latitude range
                if -90 <= lat_float <= 90:
                    return lat_float
                LOGGER.warning("Invalid latitude value: %s", lat)
            except (ValueError, TypeError):
                LOGGER.warning("Invalid latitude format: %s", lat)
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude of the device."""
        if not self.has_position:
            return None
        lon = self._device_gps_data.get("Longitude")
        if lon is not None:
            try:
                lon_float = float(lon)
                # Validate longitude range
                if -180 <= lon_float <= 180:
                    return lon_float
                LOGGER.warning("Invalid longitude value: %s", lon)
            except (ValueError, TypeError):
                LOGGER.warning("Invalid longitude format: %s", lon)
        return None

    @property
    def gps_accuracy(self) -> int:
        """Return GPS accuracy in meters."""
        accuracy = self._device_gps_data.get("GPSAccuracy", 0)
        try:
            return int(accuracy)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid GPS accuracy value: %s", accuracy)
            return 0
    
    @property
    def network_signal(self) -> int | None:
        """Return network signal strength as percentage."""
        signal = self._device_gps_data.get("NetworkQuality")
        if signal is None:
            return None
        try:
            return int(signal)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid network signal value: %s", signal)
            return None
    
    @property
    def internal_battery(self) -> int | None:
        """Return internal battery level as percentage."""
        battery_str = self._device_gps_data.get("BatteryPercentage")
        if battery_str is None:
            return None
            
        if isinstance(battery_str, (int, float)):
            return int(battery_str)
            
        if isinstance(battery_str, str):
            try:
                # Remove the '%' character and any whitespace, then convert to int
                clean_str = battery_str.strip(" %")
                battery_int = int(clean_str)
                # Validate percentage range
                if 0 <= battery_int <= 100:
                    return battery_int
                LOGGER.warning("Battery percentage out of range: %s", battery_int)
            except (ValueError, TypeError):
                LOGGER.warning("Invalid battery percentage format: %s", battery_str)
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
            course_int = int(course)
            # Validate course range (0-359 degrees)
            if 0 <= course_int <= 359:
                return course_int
            LOGGER.warning("Course value out of range: %s", course_int)
            return 0
        except (ValueError, TypeError):
            LOGGER.warning("Invalid course value: %s", course)
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