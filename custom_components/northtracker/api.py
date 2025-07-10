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
        self.rate_limit = int(response.headers.get("X-RateLimit-Limit", self.rate_limit))
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", self.rate_limit_remaining))

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        if not self._token or (self._token_expires and datetime.now() >= self._token_expires):
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
        if retry_count > 0:
            await asyncio.sleep(min(2 ** retry_count, 30))  # Exponential backoff, max 30s

        try:
            headers = self.http_headers.copy()
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            timeout = aiohttp.ClientTimeout(total=30)
            
            if method.upper() == "GET":
                async with self.session.get(url, headers=headers, timeout=timeout) as response:
                    await self._update_rate_limits(response)
                    
                    if response.status == 401 and retry_count == 0:
                        # Token might be expired, try to re-authenticate
                        self._token = None
                        await self._ensure_authenticated()
                        return await self._request(method, url, payload, retry_count + 1, max_retries)
                    
                    if response.status == 429:
                        if retry_count < max_retries:
                            LOGGER.warning("Rate limit exceeded, retrying in %d seconds", 2 ** (retry_count + 1))
                            return await self._request(method, url, payload, retry_count + 1, max_retries)
                        raise RateLimitError("Rate limit exceeded")
                    
                    response.raise_for_status()
                    return NorthTrackerResponse(await response.json())
            else:
                async with self.session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                    await self._update_rate_limits(response)
                    
                    if response.status == 401 and retry_count == 0:
                        # Token might be expired, try to re-authenticate
                        self._token = None
                        await self._ensure_authenticated()
                        return await self._request(method, url, payload, retry_count + 1, max_retries)
                    
                    if response.status == 429:
                        if retry_count < max_retries:
                            LOGGER.warning("Rate limit exceeded, retrying in %d seconds", 2 ** (retry_count + 1))
                            return await self._request(method, url, payload, retry_count + 1, max_retries)
                        raise RateLimitError("Rate limit exceeded")
                    
                    response.raise_for_status()
                    return NorthTrackerResponse(await response.json())

        except asyncio.TimeoutError as err:
            if retry_count < max_retries:
                LOGGER.warning("Request timeout, retrying (%d/%d)", retry_count + 1, max_retries)
                return await self._request(method, url, payload, retry_count + 1, max_retries)
            raise APIError(f"Request timeout after {max_retries} retries") from err
        except aiohttp.ClientError as err:
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
        url = f"{self.base_url}/login"
        payload = {"username": username, "password": password, "remember_me": False, "subsiteid": 0}
        
        try:
            resp = await self._request("POST", url, payload)
            if resp.success:
                self._token = resp.data.get('user', {}).get('token', '')
                # Set token expiration to 23 hours from now (assuming 24h validity)
                self._token_expires = datetime.now() + timedelta(hours=23)
                LOGGER.debug("Successfully authenticated with North-Tracker API")
            else:
                raise AuthenticationError("Login failed: Invalid response from server")
        except Exception as err:
            if isinstance(err, (AuthenticationError, APIError, RateLimitError)):
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
        url = f"{self.base_url}/user/terminal/get-all-units-details"
        return await self._get_data(url)

    async def get_realtime_tracking(self) -> NorthTrackerResponse:
        """Fetch real-time location data for all devices."""
        url = f"{self.base_url}/user/realtimetracking/get?lang=en"
        return await self._get_data(url)

    async def get_unit_details(self, device_id: int, device_type: str) -> NorthTrackerResponse:
        """Get detailed information for a specific unit."""
        url = f"{self.base_url}/user/terminal/edit-terminal"
        return await self._post_data(url, {"device_id": device_id, "device_type": device_type})
    
    async def get_unit_features(self, device_imei: str) -> NorthTrackerResponse:
        """Get unit features by IMEI."""
        url = f"{self.base_url}/user/terminal/get-unit-features"
        return await self._post_data(url, {"Imei": device_imei})

    async def get_unit_lock_status(self, device_id: int) -> NorthTrackerResponse:
        """Get the lock status of a unit."""
        url = f"{self.base_url}/user/terminal/access/lockstatus"
        return await self._post_data(url, {"terminal_id": device_id})

    async def input_turn_on(self, device_id: int, input_number: int) -> NorthTrackerResponse:
        """Turn on a digital input."""
        url = f"{self.base_url}/user/terminal/dinsetting/sendmsgg"
        payload = {"terminal_id": device_id, "dinnumber": input_number}
        return await self._post_data(url, payload)
    
    async def input_turn_off(self, device_id: int, input_number: int) -> NorthTrackerResponse:
        """Turn off a digital input."""
        url = f"{self.base_url}/user/terminal/dinsetting/sendmsgg"
        payload = {"terminal_id": device_id, "dinnumber": input_number}
        return await self._post_data(url, payload)

    async def output_turn_on(self, device_id: int, output_number: int) -> NorthTrackerResponse:
        """Turn on a digital output."""
        url = f"{self.base_url}/user/terminal/relaysetting/sendmsg"
        payload = {"terminal_id": device_id, "doutnumber": output_number, "doutvalue": 1}
        return await self._post_data(url, payload)

    async def output_turn_off(self, device_id: int, output_number: int) -> NorthTrackerResponse:
        """Turn off a digital output."""
        url = f"{self.base_url}/user/terminal/relaysetting/sendmsg"
        payload = {"terminal_id": device_id, "doutnumber": output_number, "doutvalue": 0}
        return await self._post_data(url, payload)

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
    def data(self) -> dict[str, Any]:
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
        self._last_update: datetime | None = None

    async def async_update(self) -> None:
        """Update device with latest information from the API."""
        try:
            # Get detailed device information
            resp_details = await self.tracker.get_unit_details(self.id, self.device_type)
            if resp_details.success:
                self._device_data_extra = resp_details.data
            else:
                LOGGER.warning("Failed to fetch device details for %s", self.name)

            # Get lock status
            resp_lock = await self.tracker.get_unit_lock_status(self.id)
            if resp_lock.success:
                self._device_lock_data = resp_lock.data
            else:
                LOGGER.warning("Failed to fetch lock status for %s", self.name)
                
            self._last_update = datetime.now()
            
        except Exception as err:
            LOGGER.error("Error updating device %s: %s", self.name, err)
            raise

    def update_gps_data(self, gps_data: dict[str, Any]) -> None:
        """Update the device with real-time location data."""
        self._device_gps_data = gps_data

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        # Consider device available if we have basic data
        return bool(self._device_data.get("ID"))

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
    def gps_signal(self) -> int:
        """Return GPS signal strength as percentage."""
        return self._device_data.get("GPS", 0)

    @property
    def last_seen(self) -> str | None:
        """Return the last seen timestamp."""
        return self._device_data.get("LastSeen")

    @property
    def battery_voltage(self) -> float | None:
        """Return battery voltage."""
        voltage = self._device_data.get("BatteryVoltage")
        if voltage is not None:
            try:
                return float(voltage)
            except (ValueError, TypeError):
                LOGGER.warning("Invalid battery voltage value: %s", voltage)
        return None

    @property
    def odometer(self) -> float:
        """Return odometer reading in kilometers."""
        odometer = self._device_data.get("Odometer", 0)
        try:
            return float(odometer)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid odometer value: %s", odometer)
            return 0.0
    
    @property
    def alarm_status(self) -> bool:
        """Return alarm status."""
        return self._device_lock_data.get("lockedstatus", False)

    @property
    def lock_status(self) -> bool:
        """Return lock status."""
        return self._device_lock_data.get("lockedstatus", False)
    
    @property
    def report_frequency(self) -> int:
        """Return report frequency in seconds."""
        try:
            terminal_data = self._device_data_extra.get("terminal", {})
            frequency = terminal_data.get("ReportFrequency", 0)
            return int(frequency)
        except (ValueError, TypeError, AttributeError):
            LOGGER.warning("Invalid report frequency value")
            return 0
    
    @property
    def input_status_2(self) -> bool:
        """Return the state of digital input 2."""
        return self._device_data.get("Din2Status") == "On"

    @property
    def input_status_3(self) -> bool:
        """Return the state of digital input 3."""
        return self._device_data.get("Din3Status") == "On"

    @property
    def output_status_1(self) -> bool:
        """Return the state of digital output 1."""
        return self._device_data.get("Dout1Status") == "On"

    @property
    def output_status_2(self) -> bool:
        """Return the state of digital output 2."""
        return self._device_data.get("Dout2Status") == "On"

    @property
    def output_status_3(self) -> bool:
        """Return the state of digital output 3."""
        return self._device_data.get("Dout3Status") == "On"
    
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
    def network_signal(self) -> int:
        """Return network signal strength as percentage."""
        signal = self._device_gps_data.get("NetworkQuality", 0)
        try:
            return int(signal)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid network signal value: %s", signal)
            return 0
    
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