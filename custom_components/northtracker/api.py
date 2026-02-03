"""North-Tracker API Client."""
from __future__ import annotations

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Any

from .const import (
    LOGGER, 
    API_BASE_URL, 
    API_TIMEOUT, 
    API_MAX_RETRIES, 
    API_RATE_LIMIT_WARNING_THRESHOLD,
    API_TIMEZONE,
    LOGGER_TOKEN_PREVIEW_LENGTH,
    DEFAULT_BATTERY_LOW_THRESHOLD
)


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
        self.base_url = API_BASE_URL
        self.http_headers = {
            "Content-Type": "application/json",
            "Timezone": API_TIMEZONE,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Request-Type": "web",
        }
        self.rate_limit = 0
        self.rate_limit_remaining = 0
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._username: str | None = None
        self._password: str | None = None

    @property
    def is_authenticated(self) -> bool:
        """Return True if the client has a valid authentication token."""
        return self._token is not None

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
            if usage_percent > API_RATE_LIMIT_WARNING_THRESHOLD:
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
        max_retries: int = API_MAX_RETRIES
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
            wait_time = min(2 ** retry_count, API_TIMEOUT)
            LOGGER.debug("Waiting %d seconds before retry", wait_time)
            await asyncio.sleep(wait_time)

        try:
            headers = self.http_headers.copy()
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
                LOGGER.debug("Using authentication token (preview: %s...)", self._token[:LOGGER_TOKEN_PREVIEW_LENGTH])
            else:
                LOGGER.debug("No authentication token available")

            # Debug: Log all headers being sent (but mask authorization)
            debug_headers = headers.copy()
            if "Authorization" in debug_headers:
                debug_headers["Authorization"] = f"Bearer {self._token[:LOGGER_TOKEN_PREVIEW_LENGTH]}..." if self._token else "None"
            LOGGER.debug("Request headers: %s", debug_headers)

            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
            
            if method.upper() == "GET":
                async with self.session.get(url, headers=headers, timeout=timeout) as response:
                    await self._update_rate_limits(response)
                    LOGGER.debug("GET response: status=%d, content-type=%s, rate_limit=%d/%d", 
                               response.status, response.headers.get('Content-Type'), 
                               self.rate_limit_remaining, self.rate_limit)
                    
                    # Handle authentication errors and potential token expiration (401 + 5xx)
                    if ((response.status == 401) or (500 <= response.status < 600)) and retry_count == 0 and self._token:
                        LOGGER.warning("Authentication/server error %d - attempting re-authentication", response.status)
                        # Save current token for comparison
                        old_token = self._token
                        self._token = None
                        try:
                            await self._ensure_authenticated()
                            # Only retry if we got a new token
                            if self._token != old_token:
                                LOGGER.debug("Got new token after %d error, retrying request", response.status)
                                return await self._request(method, url, payload, retry_count + 1, max_retries)
                        except AuthenticationError:
                            LOGGER.warning("Re-authentication failed after %d error, continuing with original error", response.status)
                            # Restore old token and continue with original error handling
                            self._token = old_token
                    
                    if response.status == 429:
                        if retry_count < max_retries:
                            wait_time = 2 ** (retry_count + 1)
                            LOGGER.warning("Rate limit exceeded, retrying in %d seconds", wait_time)
                            return await self._request(method, url, payload, retry_count + 1, max_retries)
                        raise RateLimitError("Rate limit exceeded")
                    
                    response.raise_for_status()
                    response_data = await response.json()
                    LOGGER.debug("GET response data keys: %s", list(response_data.keys()) if isinstance(response_data, dict) else "non-dict")
                    LOGGER.debug("Full GET response data: %s", response_data)
                    return NorthTrackerResponse(response_data)
            else:
                async with self.session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                    await self._update_rate_limits(response)
                    LOGGER.debug("POST response: status=%d, content-type=%s, rate_limit=%d/%d", 
                               response.status, response.headers.get('Content-Type'),
                               self.rate_limit_remaining, self.rate_limit)
                    
                    # Handle authentication errors and potential token expiration (401 + 5xx)
                    if ((response.status == 401) or (500 <= response.status < 600)) and retry_count == 0 and self._token:
                        LOGGER.warning("Authentication/server error %d - attempting re-authentication", response.status)
                        # Save current token for comparison
                        old_token = self._token
                        self._token = None
                        try:
                            await self._ensure_authenticated()
                            # Only retry if we got a new token
                            if self._token != old_token:
                                LOGGER.debug("Got new token after %d error, retrying request", response.status)
                                return await self._request(method, url, payload, retry_count + 1, max_retries)
                        except AuthenticationError:
                            LOGGER.warning("Re-authentication failed after %d error, continuing with original error", response.status)
                            # Restore old token and continue with original error handling
                            self._token = old_token
                    
                    if response.status == 429:
                        if retry_count < max_retries:
                            wait_time = 2 ** (retry_count + 1)
                            LOGGER.warning("Rate limit exceeded, retrying in %d seconds", wait_time)
                            return await self._request(method, url, payload, retry_count + 1, max_retries)
                        raise RateLimitError("Rate limit exceeded")
                    
                    response.raise_for_status()
                    response_data = await response.json()
                    LOGGER.debug("POST response data keys: %s", list(response_data.keys()) if isinstance(response_data, dict) else "non-dict")
                    LOGGER.debug("Full POST response data: %s", response_data)
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
            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
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
                    LOGGER.debug("Token preview: %s...", self._token[:LOGGER_TOKEN_PREVIEW_LENGTH] if self._token else "empty")
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

    async def set_low_battery_alert(self, device_imei: str, enabled: bool, threshold: float = DEFAULT_BATTERY_LOW_THRESHOLD) -> NorthTrackerResponse:
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

    # -------------------------------------------------------------------------
    # Geofence Methods
    # -------------------------------------------------------------------------

    async def get_geofences(self) -> NorthTrackerResponse:
        """Get all geofences for the user.
        
        Returns:
            Response containing list of geofences with their status.
        """
        LOGGER.debug("Fetching geofences from API")
        url = f"{self.base_url}/user/geofence/get/list"
        response = await self._get_data(url)
        if response.success:
            geofences = response.data.get("geofences", [])
            LOGGER.debug("Successfully fetched %d geofences", len(geofences))
        else:
            LOGGER.warning("Failed to fetch geofences")
        return response

    async def set_geofence_status(
        self, geofence_id: int, group_identifier: str, enabled: bool
    ) -> NorthTrackerResponse:
        """Enable or disable a geofence.
        
        Args:
            geofence_id: The geofence ID
            group_identifier: The group identifier for the geofence
            enabled: True to enable, False to disable
            
        Returns:
            Response indicating success/failure
        """
        status = "1" if enabled else "0"
        LOGGER.debug(
            "Setting geofence %d status to %s (enabled=%s)", 
            geofence_id, status, enabled
        )
        url = f"{self.base_url}/user/geofence/state/group-update"
        payload = {
            "status": status,
            "geofence_id": geofence_id,
            "group_identifier": group_identifier,
        }
        response = await self._post_data(url, payload)
        if response.success:
            LOGGER.debug("Successfully set geofence %d status to %s", geofence_id, status)
        else:
            LOGGER.warning("Failed to set geofence %d status", geofence_id)
        return response

    async def set_all_geofences_status(
        self, terminal_id: int, enabled: bool
    ) -> list[NorthTrackerResponse]:
        """Enable or disable all geofences for a specific terminal.
        
        Args:
            terminal_id: The terminal/device ID
            enabled: True to enable all, False to disable all
            
        Returns:
            List of responses for each geofence update
        """
        LOGGER.debug(
            "Setting all geofences for terminal %d to enabled=%s", 
            terminal_id, enabled
        )
        
        # First get all geofences
        geofences_response = await self.get_geofences()
        if not geofences_response.success:
            LOGGER.error("Failed to fetch geofences for bulk update")
            return [geofences_response]
        
        geofences = geofences_response.data.get("geofences", [])
        
        # Filter geofences for this terminal
        terminal_geofences = [
            gf for gf in geofences if gf.get("TerminalID") == terminal_id
        ]
        
        if not terminal_geofences:
            LOGGER.debug("No geofences found for terminal %d", terminal_id)
            return []
        
        LOGGER.debug(
            "Found %d geofences for terminal %d, updating...", 
            len(terminal_geofences), terminal_id
        )
        
        # Update each geofence
        responses = []
        for gf in terminal_geofences:
            response = await self.set_geofence_status(
                geofence_id=gf.get("ID"),
                group_identifier=gf.get("GroupIdentifier", ""),
                enabled=enabled,
            )
            responses.append(response)
        
        return responses

    async def get_geofence_status_for_terminal(
        self, terminal_id: int
    ) -> bool | None:
        """Check if all geofences for a terminal are enabled.
        
        Args:
            terminal_id: The terminal/device ID
            
        Returns:
            True if all geofences are enabled,
            False if any geofence is disabled,
            None if no geofences exist for this terminal
        """
        geofences_response = await self.get_geofences()
        if not geofences_response.success:
            LOGGER.warning("Failed to fetch geofences for status check")
            return None
        
        geofences = geofences_response.data.get("geofences", [])
        terminal_geofences = [
            gf for gf in geofences if gf.get("TerminalID") == terminal_id
        ]
        
        if not terminal_geofences:
            LOGGER.debug("No geofences found for terminal %d", terminal_id)
            return None
        
        # Check if all geofences are enabled (Status == "1")
        all_enabled = all(
            gf.get("Status") == "1" for gf in terminal_geofences
        )
        LOGGER.debug(
            "Geofence status for terminal %d: all_enabled=%s (checked %d geofences)",
            terminal_id, all_enabled, len(terminal_geofences)
        )
        return all_enabled


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

