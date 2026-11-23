"""Client for the Nature Remo Cloud API."""

from datetime import UTC, datetime
import json
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_TIMEOUT

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=API_TIMEOUT)
_RATE_LIMIT_RESET_HEADER = "X-Rate-Limit-Reset"


class NatureRemoError(Exception):
    """Base error for the Nature Remo API."""


class NatureRemoConnectionError(NatureRemoError):
    """The API could not be reached or did not answer in time."""


class NatureRemoApiError(NatureRemoError):
    """The API answered with an error or an unusable response."""

    def __init__(self, status: int, message: str) -> None:
        """Keep the HTTP status and the message reported by the API."""
        super().__init__(f"{message} (HTTP {status})")
        self.status = status
        self.message = message


class NatureRemoAuthError(NatureRemoApiError):
    """The access token was rejected."""


class NatureRemoRateLimitError(NatureRemoApiError):
    """The request rate limit was exceeded."""

    def __init__(self, status: int, message: str, reset: datetime | None) -> None:
        """Keep the time at which the rate limit window resets, if reported."""
        super().__init__(status, message)
        self.reset = reset


class NatureRemoAPI:
    """Nature Remo API client."""

    def __init__(self, access_token: str, session: aiohttp.ClientSession) -> None:
        """Init API client."""
        self._access_token = access_token
        self._session = session

    async def get_user(self) -> dict[str, Any]:
        """Return the account that owns the access token."""
        return _expect(await self._request("GET", "/1/users/me"), dict)

    async def get_appliances(self) -> list[dict[str, Any]]:
        """Return all appliances registered to the account."""
        return _expect(await self._request("GET", "/1/appliances"), list)

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return all Nature Remo devices registered to the account."""
        return _expect(await self._request("GET", "/1/devices"), list)

    async def set_aircon_settings(
        self, appliance_id: str, settings: dict[str, str]
    ) -> dict[str, Any]:
        """Update air conditioner settings and return the resulting settings."""
        return _expect(
            await self._request(
                "POST", f"/1/appliances/{appliance_id}/aircon_settings", settings
            ),
            dict,
        )

    async def _request(
        self, method: str, path: str, data: dict[str, str] | None = None
    ) -> Any:
        """Send a request and return the decoded body, raising on any failure."""
        _LOGGER.debug("Request %s %s data=%s", method, path, data)
        try:
            response = await self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {self._access_token}"},
                data=data,
                timeout=_TIMEOUT,
            )
            async with response:
                status = response.status
                headers = response.headers
                text = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NatureRemoConnectionError(
                f"Error communicating with the Nature Remo API: {err or type(err).__name__}"
            ) from err

        if status == 401:
            raise NatureRemoAuthError(status, _error_message(text, "Unauthorized"))
        if status == 429:
            raise NatureRemoRateLimitError(
                status,
                _error_message(text, "Rate limit exceeded"),
                _rate_limit_reset(headers),
            )
        if status >= 400:
            raise NatureRemoApiError(status, _error_message(text, "Request failed"))

        try:
            return json.loads(text)
        except ValueError as err:
            raise NatureRemoApiError(status, "Response is not valid JSON") from err


def _expect[_T](body: Any, expected: type[_T]) -> _T:
    """Check that a successful response has the expected top-level type."""
    if not isinstance(body, expected):
        raise NatureRemoApiError(
            200, f"Unexpected response: expected {expected.__name__}"
        )
    return body


def _error_message(text: str, default: str) -> str:
    """Extract the message from an API error body."""
    try:
        body = json.loads(text)
    except ValueError:
        return default
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    return default


def _rate_limit_reset(headers: Any) -> datetime | None:
    """Return when the rate limit window resets, from the response headers."""
    try:
        return datetime.fromtimestamp(int(headers[_RATE_LIMIT_RESET_HEADER]), UTC)
    except (KeyError, ValueError, OverflowError, OSError):
        return None
