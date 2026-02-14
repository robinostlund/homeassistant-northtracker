---
applyTo: "custom_components/northtracker/api.py"
---

# API Client Instructions

## API Structure

The NorthTracker API client handles:

- Authentication (login, token refresh)
- Device data fetching
- Rate limiting and retries
- Error handling

## Making API Requests

Always use the internal request methods with proper error handling:

```python
async def _request(
    self,
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Make an API request with authentication and error handling."""
    # Ensure we have a valid token
    await self._ensure_authenticated()
    
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {self._token}"}
    
    try:
        async with self._session.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status == 401:
                raise NorthTrackerAuthError("Token expired")
            if resp.status >= 400:
                raise NorthTrackerApiError(f"API error: {resp.status}")
            return await resp.json()
    except aiohttp.ClientError as err:
        raise NorthTrackerApiError(f"Connection error: {err}")
```

## Error Types

Use specific exception types:

```python
class NorthTrackerError(Exception):
    """Base exception for NorthTracker."""

class NorthTrackerAuthError(NorthTrackerError):
    """Authentication error."""

class NorthTrackerApiError(NorthTrackerError):
    """API request error."""

class NorthTrackerRateLimitError(NorthTrackerApiError):
    """Rate limit exceeded."""
```

## Token Management

- Store token and expiry time
- Refresh token before it expires
- Handle token refresh failures gracefully

```python
async def _ensure_authenticated(self) -> None:
    """Ensure we have a valid authentication token."""
    if self._token and self._token_expiry > datetime.now():
        return
    
    await self._login()
```

## Rate Limiting

Implement exponential backoff for retries:

```python
async def _request_with_retry(self, ...) -> dict[str, Any]:
    """Make request with retry logic."""
    for attempt in range(API_MAX_RETRIES):
        try:
            return await self._request(...)
        except NorthTrackerRateLimitError:
            if attempt < API_MAX_RETRIES - 1:
                delay = API_RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
            else:
                raise
```

## Logging API Calls

Log requests but mask sensitive data:

```python
LOGGER.debug(
    "API request: %s %s",
    method,
    endpoint,
)

# Never log tokens or passwords
LOGGER.debug("Login successful for user: %s", username)  # Good
LOGGER.debug("Token: %s", token)  # BAD - never do this
```
