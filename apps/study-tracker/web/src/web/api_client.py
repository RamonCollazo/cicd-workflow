"""HTTP client for the Study Tracker API.

Uses a ``requests.Session`` so connections are reused across requests,
and applies a GET-only retry policy (transient 502/503/504 + connect/read
errors). POST is **not** retried because there's no idempotency key — a
retried session-create could duplicate the row server-side.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised when the API is unreachable or returns an unexpected response."""


class ApiClient:
    """Thin client for the Study Tracker API."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        retries: int,
        backoff: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._session = requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=backoff,
            status_forcelist=[502, 503, 504],
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    @property
    def base_url(self) -> str:
        return self._base_url

    def get_sessions(self) -> list[dict[str, Any]]:
        """Fetch all study sessions. Raises ``ApiError`` on failure."""
        url = f"{self._base_url}/sessions"
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ApiError(f"GET {url} failed: {e}") from e
        except ValueError as e:  # bad JSON
            raise ApiError(f"GET {url} returned invalid JSON: {e}") from e

    def create_session(self, minutes: int, tag: str) -> None:
        """Create a study session. Not retried (no idempotency key).

        Raises ``ApiError`` on failure.
        """
        url = f"{self._base_url}/sessions"
        payload = {"minutes": minutes, "tag": tag}
        try:
            response = self._session.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ApiError(f"POST {url} failed: {e}") from e

    def health(self) -> bool:
        """Return True when the API responds 2xx to /health, else False."""
        url = f"{self._base_url}/health"
        try:
            response = self._session.get(url, timeout=self._timeout)
            return response.ok
        except requests.RequestException:
            return False

    def close(self) -> None:
        """Close the underlying ``requests.Session``."""
        self._session.close()
