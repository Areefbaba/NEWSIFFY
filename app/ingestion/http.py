import asyncio

import httpx

from app.ingestion.errors import FetchError


RETRYABLE_STATUS_CODES = {429, 500, 501, 502, 503, 504}


async def fetch_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
    timeout_seconds: float,
    retry_attempts: int = 3,
) -> bytes:
    """Fetch bytes with bounded retries for transient HTTP/network failures."""
    attempts = max(1, retry_attempts)
    for attempt in range(1, attempts + 1):
        try:
            response = await client.get(url, params=params, timeout=timeout_seconds)
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            if attempt == attempts:
                raise FetchError(f"Request to {url} failed after {attempts} attempts") from error
            await asyncio.sleep(0)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt == attempts:
                raise FetchError(f"Request to {url} returned retryable HTTP {response.status_code}")
            await asyncio.sleep(0)
            continue
        if response.is_error:
            raise FetchError(f"Request to {url} returned HTTP {response.status_code}")
        return response.content

    raise FetchError(f"Request to {url} failed")
