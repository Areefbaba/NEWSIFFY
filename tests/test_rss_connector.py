import asyncio

import httpx
import pytest

from app.ingestion.config import SourceDefinition
from app.ingestion.errors import FetchError, MalformedContentError
from app.ingestion.rss import RSSConnector


RSS_FEED = b"""<?xml version='1.0'?>
<rss version='2.0'><channel><title>AI Updates</title>
<item><title>  Unicode AI \xe2\x9c\xa8  </title><link>HTTPS://Example.COM/article#section</link><pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate><author>Ada Lovelace</author><description>  A  useful  summary. </description></item>
<item><title>Second item</title><link>https://example.com/second</link></item>
<item><title>Missing link</title></item>
</channel></rss>"""

ATOM_FEED = b"""<feed xmlns='http://www.w3.org/2005/Atom'><title>Atom AI</title>
<entry><title>Atom release</title><link rel='self' href='https://example.com/self'/><link href='https://example.com/atom'/><published>2024-02-01T10:00:00Z</published><author><name>Grace Hopper</name></author><summary>Atom summary</summary></entry>
</feed>"""


def source() -> SourceDefinition:
    return SourceDefinition(name="Test Feed", source_type="rss", url="https://example.com/feed", content_type="tool_release")


def fetch_payload(payload: bytes) -> list:
    async def run() -> list:
        transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
        async with httpx.AsyncClient(transport=transport) as client:
            return await RSSConnector(source(), client).fetch()
    return asyncio.run(run())


def test_rss_normalizes_multiple_entries_and_skips_bad_entry() -> None:
    items = fetch_payload(RSS_FEED)
    assert len(items) == 2
    assert items[0].title == "Unicode AI ✨"
    assert str(items[0].url) == "https://example.com/article"
    assert items[0].authors == ["Ada Lovelace"]
    assert items[0].summary == "A useful summary."
    assert items[1].published_at is None
    assert items[0].content_type == "tool_release"


def test_atom_is_supported() -> None:
    items = fetch_payload(ATOM_FEED)
    assert len(items) == 1
    assert str(items[0].url) == "https://example.com/atom"
    assert items[0].authors == ["Grace Hopper"]


def test_malformed_feed_is_reported() -> None:
    with pytest.raises(MalformedContentError):
        fetch_payload(b"<rss><channel>")


def test_retryable_status_is_retried() -> None:
    attempts = 0

    async def run() -> list:
        nonlocal attempts
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(429 if attempts == 1 else 200, content=ATOM_FEED)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await RSSConnector(source(), client, retry_attempts=2).fetch()

    assert len(asyncio.run(run())) == 1
    assert attempts == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
def test_http_errors_are_reported(status: int) -> None:
    async def run() -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(status))
        async with httpx.AsyncClient(transport=transport) as client:
            await RSSConnector(source(), client, retry_attempts=1).fetch()
    with pytest.raises(FetchError):
        asyncio.run(run())
