"""Shared HTTP client with retry logic and rate limiting."""

import logging
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

logger = logging.getLogger(__name__)


def create_session(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    extra_headers: Optional[dict] = None,
    pool_size: int = 10,
) -> requests.Session:
    """Create a requests Session with automatic retry on transient errors.

    Retries on 429 (rate limited) and 500/502/503/504 (server errors)
    with exponential backoff.
    """
    session = requests.Session()

    retry = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=pool_size,
        pool_maxsize=pool_size,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    session.headers.update(headers)

    return session


def fetch_page(
    session: requests.Session,
    url: str,
    method: str = "GET",
    timeout: int = 30,
    delay: float = 0,
    **kwargs,
) -> requests.Response:
    """Fetch a URL with logging and optional rate-limit delay.

    Args:
        session: requests Session (from create_session).
        url: URL to fetch.
        method: HTTP method (GET, POST, etc.).
        timeout: Request timeout in seconds.
        delay: Seconds to sleep before the request (rate limiting).
        **kwargs: Passed to session.request (data, params, etc.).

    Returns:
        requests.Response on success.

    Raises:
        requests.RequestException on failure.
    """
    if delay > 0:
        time.sleep(delay)

    logger.debug("Fetching %s %s", method, url)
    resp = session.request(method, url, timeout=timeout, **kwargs)
    resp.raise_for_status()
    logger.debug("Got %d (%d bytes)", resp.status_code, len(resp.content))
    return resp
