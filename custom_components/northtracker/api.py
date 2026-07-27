"""NorthTracker API Client."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_ERROR_BODY_PREVIEW_LENGTH,
    API_MAX_REALTIME_PAGES,
    API_MAX_RETRIES,
    API_RATE_LIMIT_WARNING_THRESHOLD,
    API_REAUTH_COOLDOWN,
    API_TIMEOUT,
    API_TIMEZONE,
    LOGGER,
    LOGGER_TOKEN_PREVIEW_LENGTH,
)


def _as_int(value: Any, default: int) -> int:
    """Return value as int, falling back to default for anything unparsable."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class NorthTrackerException(Exception):
    """Base exception for NorthTracker API errors."""


class AuthenticationError(NorthTrackerException):
    """Exception for authentication errors."""


class RateLimitError(NorthTrackerException):
    """Exception for rate limit errors."""


class APIError(NorthTrackerException):
    """Exception for general API errors."""


class NorthTracker:
    """NorthTracker API client with improved error handling and token management."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the NorthTracker API client."""
        self.session = session
        self.base_url = API_BASE_URL
        self.http_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Timezone": API_TIMEZONE,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Request-Type": "web",
        }
        self.rate_limit = 0
        self.rate_limit_remaining = 0
        self._token: str | None = None
        # Monotonic deadline (time.monotonic) after which the token is considered expired
        self._token_expires: float | None = None
        # Monotonic deadline before which a 5xx must not trigger a re-authentication
        self._server_error_reauth_after: float = 0.0
        self._username: str | None = None
        self._password: str | None = None

    @property
    def is_authenticated(self) -> bool:
        """Return True if the client has a valid authentication token."""
        return self._token is not None

    async def _update_rate_limits(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit information from response headers."""
        old_remaining = self.rate_limit_remaining
        self.rate_limit = int(
            response.headers.get("X-RateLimit-Limit", self.rate_limit)
        )
        self.rate_limit_remaining = int(
            response.headers.get("X-RateLimit-Remaining", self.rate_limit_remaining)
        )

        LOGGER.debug(
            "Rate limit info updated: %d/%d remaining (was %d)",
            self.rate_limit_remaining,
            self.rate_limit,
            old_remaining,
        )

        # Warn if rate limit is getting low
        if self.rate_limit > 0:
            usage_percent = (
                (self.rate_limit - self.rate_limit_remaining) / self.rate_limit
            ) * 100
            if usage_percent > API_RATE_LIMIT_WARNING_THRESHOLD:
                LOGGER.warning(
                    "Rate limit usage high: %.1f%% (%d/%d requests used)",
                    usage_percent,
                    self.rate_limit - self.rate_limit_remaining,
                    self.rate_limit,
                )

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        LOGGER.debug("Checking authentication status...")
        if not self._token:
            LOGGER.debug("No token available, need to authenticate")
        elif self._token_expires and time.monotonic() >= self._token_expires:
            LOGGER.debug("Token expired, need to re-authenticate")
        else:
            LOGGER.debug("Token is still valid")
            return

        if not self._username or not self._password:
            raise AuthenticationError("No credentials available for authentication")
        await self._login(self._username, self._password)

    async def _try_reauthenticate(self, status: int, retry_count: int) -> bool:
        """Re-authenticate after a 401/5xx and return True if the request should be retried.

        A 401 always deserves a fresh token. The API has also been seen answering
        5xx for a stale token, so those get one retry too - but at most once per
        API_REAUTH_COOLDOWN, so that a genuinely broken endpoint does not make us
        log in again for every single request it fails.
        """
        if retry_count != 0 or not self._token:
            return False

        if status != 401:
            if time.monotonic() < self._server_error_reauth_after:
                LOGGER.debug(
                    "Server error %d - not re-authenticating (cooldown active)", status
                )
                return False
            self._server_error_reauth_after = time.monotonic() + API_REAUTH_COOLDOWN
            LOGGER.debug("Server error %d - trying a fresh token once", status)
        else:
            LOGGER.debug("Authentication error 401 - attempting re-authentication")

        old_token = self._token
        self._token = None
        try:
            await self._ensure_authenticated()
        except AuthenticationError:
            LOGGER.warning(
                "Re-authentication failed after %d error, continuing with original error",
                status,
            )
            # Restore old token and continue with original error handling
            self._token = old_token
            return False

        # Only retry if we actually got a new token
        return self._token != old_token

    async def _log_error_body(self, response: aiohttp.ClientResponse) -> None:
        """Log the body of a failed response - it usually explains the failure."""
        try:
            body = await response.text()
        except (aiohttp.ClientError, UnicodeDecodeError) as err:
            LOGGER.debug("Could not read error body from %s: %s", response.url, err)
            return
        LOGGER.debug(
            "Error %d body from %s: %s",
            response.status,
            response.url,
            body[:API_ERROR_BODY_PREVIEW_LENGTH],
        )

    async def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        retry_count: int = 0,
        max_retries: int = API_MAX_RETRIES,
    ) -> NorthTrackerResponse:
        """Make an authenticated request with retry logic."""
        LOGGER.debug(
            "Making %s request to %s (attempt %d/%d)",
            method,
            url,
            retry_count + 1,
            max_retries + 1,
        )

        if payload:
            # Log payload but mask sensitive data
            safe_payload = payload.copy()
            if "password" in safe_payload:
                safe_payload["password"] = "***"
            LOGGER.debug("Request payload: %s", safe_payload)

        if retry_count > 0:
            wait_time = min(2**retry_count, API_TIMEOUT)
            LOGGER.debug("Waiting %d seconds before retry", wait_time)
            await asyncio.sleep(wait_time)

        try:
            headers = self.http_headers.copy()
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
                LOGGER.debug(
                    "Using authentication token (preview: %s...)",
                    self._token[:LOGGER_TOKEN_PREVIEW_LENGTH],
                )
            else:
                LOGGER.debug("No authentication token available")

            # Debug: Log all headers being sent (but mask authorization)
            debug_headers = headers.copy()
            if "Authorization" in debug_headers:
                debug_headers["Authorization"] = (
                    f"Bearer {self._token[:LOGGER_TOKEN_PREVIEW_LENGTH]}..."
                    if self._token
                    else "None"
                )
            LOGGER.debug("Request headers: %s", debug_headers)

            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)

            if method.upper() == "GET":
                async with self.session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    await self._update_rate_limits(response)
                    LOGGER.debug(
                        "GET response: status=%d, content-type=%s, rate_limit=%d/%d",
                        response.status,
                        response.headers.get("Content-Type"),
                        self.rate_limit_remaining,
                        self.rate_limit,
                    )

                    # Handle authentication errors and potential token expiration (401 + 5xx)
                    if (response.status == 401) or (500 <= response.status < 600):
                        await self._log_error_body(response)
                        if await self._try_reauthenticate(response.status, retry_count):
                            LOGGER.debug(
                                "Got new token after %d error, retrying request",
                                response.status,
                            )
                            return await self._request(
                                method, url, payload, retry_count + 1, max_retries
                            )

                    if response.status == 429:
                        if retry_count < max_retries:
                            wait_time = 2 ** (retry_count + 1)
                            LOGGER.warning(
                                "Rate limit exceeded, retrying in %d seconds", wait_time
                            )
                            return await self._request(
                                method, url, payload, retry_count + 1, max_retries
                            )
                        raise RateLimitError("Rate limit exceeded")

                    # A 401 that survived the re-auth attempt above means the
                    # credentials are no longer valid: surface it as an auth error
                    # so the coordinator triggers reauth instead of a plain retry.
                    if response.status == 401:
                        raise AuthenticationError("Authentication failed (HTTP 401)")

                    response.raise_for_status()
                    response_data = await response.json()
                    LOGGER.debug(
                        "GET response data keys: %s",
                        list(response_data.keys())
                        if isinstance(response_data, dict)
                        else "non-dict",
                    )
                    return NorthTrackerResponse(response_data)
            else:
                async with self.session.post(
                    url, json=payload, headers=headers, timeout=timeout
                ) as response:
                    await self._update_rate_limits(response)
                    LOGGER.debug(
                        "POST response: status=%d, content-type=%s, rate_limit=%d/%d",
                        response.status,
                        response.headers.get("Content-Type"),
                        self.rate_limit_remaining,
                        self.rate_limit,
                    )

                    # Handle authentication errors and potential token expiration (401 + 5xx)
                    if (response.status == 401) or (500 <= response.status < 600):
                        await self._log_error_body(response)
                        if await self._try_reauthenticate(response.status, retry_count):
                            LOGGER.debug(
                                "Got new token after %d error, retrying request",
                                response.status,
                            )
                            return await self._request(
                                method, url, payload, retry_count + 1, max_retries
                            )

                    if response.status == 429:
                        if retry_count < max_retries:
                            wait_time = 2 ** (retry_count + 1)
                            LOGGER.warning(
                                "Rate limit exceeded, retrying in %d seconds", wait_time
                            )
                            return await self._request(
                                method, url, payload, retry_count + 1, max_retries
                            )
                        raise RateLimitError("Rate limit exceeded")

                    # A 401 that survived the re-auth attempt above means the
                    # credentials are no longer valid: surface it as an auth error
                    # so the coordinator triggers reauth instead of a plain retry.
                    if response.status == 401:
                        raise AuthenticationError("Authentication failed (HTTP 401)")

                    response.raise_for_status()
                    response_data = await response.json()
                    LOGGER.debug(
                        "POST response data keys: %s",
                        list(response_data.keys())
                        if isinstance(response_data, dict)
                        else "non-dict",
                    )
                    return NorthTrackerResponse(response_data)

        except TimeoutError as err:
            LOGGER.debug("Request timeout after 30 seconds")
            if retry_count < max_retries:
                LOGGER.warning(
                    "Request timeout, retrying (%d/%d)", retry_count + 1, max_retries
                )
                return await self._request(
                    method, url, payload, retry_count + 1, max_retries
                )
            raise APIError(f"Request timeout after {max_retries} retries") from err
        except aiohttp.ClientError as err:
            LOGGER.debug("Client error: %s", err)
            if retry_count < max_retries:
                LOGGER.warning(
                    "Client error, retrying (%d/%d): %s",
                    retry_count + 1,
                    max_retries,
                    err,
                )
                return await self._request(
                    method, url, payload, retry_count + 1, max_retries
                )
            raise APIError(f"Client error after {max_retries} retries: {err}") from err

    async def _get_data(self, url: str) -> NorthTrackerResponse:
        """Make a GET request."""
        await self._ensure_authenticated()
        return await self._request("GET", url)

    async def _post_data(
        self, url: str, payload: dict[str, Any] | None = None
    ) -> NorthTrackerResponse:
        """Make a POST request."""
        await self._ensure_authenticated()
        return await self._request("POST", url, payload)

    async def _login(self, username: str, password: str) -> None:
        """Internal login method that sets the token."""
        LOGGER.debug("Attempting to login with username: %s", username)
        url = f"{self.base_url}/login"
        payload = {
            "username": username,
            "password": password,
            "remember_me": False,
            "subsiteid": 0,
        }

        try:
            # Make login request without authentication (bypass _get_data/_post_data)
            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
            async with self.session.post(
                url, json=payload, headers=self.http_headers, timeout=timeout
            ) as response:
                await self._update_rate_limits(response)
                LOGGER.debug(
                    "Login response: status=%d, content-type=%s",
                    response.status,
                    response.headers.get("Content-Type"),
                )

                response.raise_for_status()
                response_data = await response.json()
                resp = NorthTrackerResponse(response_data)

                if resp.success:
                    self._token = resp.data.get("user", {}).get("token", "")
                    # Set token expiration to 23 hours from now (assuming 24h validity)
                    self._token_expires = time.monotonic() + 23 * 3600
                    LOGGER.debug("Successfully authenticated, token valid for ~23h")
                    LOGGER.debug(
                        "Token preview: %s...",
                        self._token[:LOGGER_TOKEN_PREVIEW_LENGTH]
                        if self._token
                        else "empty",
                    )
                else:
                    LOGGER.error("Login failed: API returned success=False")
                    raise AuthenticationError(
                        "Login failed: Invalid response from server"
                    )

        except aiohttp.ClientError as err:
            LOGGER.error("Login failed with client error: %s", err)
            raise AuthenticationError(f"Login failed: {err}") from err
        except (ValueError, KeyError) as err:
            # Malformed/unexpected login response body
            LOGGER.error("Login failed to parse response: %s", err)
            raise AuthenticationError(f"Login failed: invalid response: {err}") from err

    async def login(self, username: str, password: str) -> bool:
        """Authenticate with the NorthTracker API and store credentials for future use."""
        self._username = username
        self._password = password
        await self._login(username, password)
        return True

    async def logout(self) -> None:
        """Logout from the NorthTracker API."""
        url = f"{self.base_url}/user/logout"
        try:
            await self._post_data(url)
        finally:
            # Clear credentials regardless of logout success
            self._token = None
            self._token_expires = None

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

    def _realtime_tracking_url(self, page: int) -> str:
        """Build the URL for one page of real-time tracking data."""
        return (
            f"{self.base_url}/user/realtimetracking/latest-units-data"
            f"?lang=en&page={page}&order_by=&order_dir=&only_marker_detail=0"
        )

    async def get_realtime_tracking(self) -> NorthTrackerResponse:
        """Fetch real-time location data for all devices.

        The unit list is paginated by the API, so every page is fetched and the
        units are merged into a single flat "gps" list.
        """
        LOGGER.debug("Fetching real-time tracking data from API")

        units: list[dict[str, Any]] = []
        payload: dict[str, Any] = {}
        page = 1

        while True:
            response = await self._get_data(self._realtime_tracking_url(page))
            if not response.success:
                LOGGER.warning(
                    "Failed to fetch real-time tracking data (page %d)", page
                )
                return response

            data = response.data if isinstance(response.data, dict) else {}
            if not payload:
                # Keep the non-paginated parts (sensor, blt, ...) from the first page
                payload = dict(data)

            gps = data.get("gps")
            if isinstance(gps, dict):
                # Laravel paginator: {"current_page": 1, "last_page": 2, "data": [...]}
                units.extend(gps.get("data") or [])
                current_page = _as_int(gps.get("current_page"), page)
                last_page = _as_int(gps.get("last_page"), page)
            else:
                # Defensive: a plain list means there is nothing to paginate
                units.extend(gps or [])
                current_page = last_page = page

            if current_page >= last_page:
                break
            if page >= API_MAX_REALTIME_PAGES:
                LOGGER.warning(
                    "Stopping after %d pages of real-time tracking data (last page: %d)",
                    page,
                    last_page,
                )
                break
            page += 1

        payload["gps"] = units
        LOGGER.debug(
            "Successfully fetched GPS data for %d devices (%d page(s))",
            len(units),
            page,
        )
        return NorthTrackerResponse({"success": True, "data": payload})

    async def get_unit_details(
        self, device_id: int, device_type: str
    ) -> NorthTrackerResponse:
        """Get detailed information for a specific unit."""
        LOGGER.debug(
            "Fetching detailed info for device %d (type: %s)", device_id, device_type
        )
        url = f"{self.base_url}/user/terminal/edit-terminal"
        response = await self._post_data(
            url, {"device_id": device_id, "device_type": device_type}
        )
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


class NorthTrackerResponse:
    """Wrapper for API responses from NorthTracker."""

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
