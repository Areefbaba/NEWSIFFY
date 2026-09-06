import asyncio
from datetime import UTC, datetime

import httpx

from app.database.models import ArticleRecord
from app.ingestion.base import SourceConnector
from app.ingestion.models import ContentType, NewsItem, SourceType
from app.ingestion.runner import IngestionRunner


class StaticConnector(SourceConnector):
    async def fetch(self) -> list[NewsItem]:
        return [
            NewsItem(
                source_name="Mock source", source_type=SourceType.RSS, content_type=ContentType.NEWS,
                title="A mocked article", url="https://example.com/mock", fetched_at=datetime.now(UTC), metadata={},
            )
        ]


def test_runner_persists_source_items_idempotently(db_session, tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text("""sources:
  - name: Mock source
    source_type: rss
    url: https://example.com/feed
""", encoding="utf-8")
    monkeypatch.setattr("app.ingestion.runner.connector_for", lambda source, client: StaticConnector())

    async def run() -> tuple:
        async with httpx.AsyncClient() as client:
            runner = IngestionRunner(db_session, config_path, client)
            return await runner.run(), await runner.run()

    first, second = asyncio.run(run())
    assert (first.sources_processed, first.items_fetched, first.inserted, first.duplicates, first.failures) == (1, 1, 1, 0, 0)
    assert (second.inserted, second.duplicates, second.failures) == (0, 1, 0)
    assert db_session.query(ArticleRecord).count() == 1


def test_runner_deduplicates_real_rss_entries(db_session, tmp_path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text("""sources:
  - name: RSS source
    source_type: rss
    url: https://example.com/feed
""", encoding="utf-8")
    feed = b"""<rss><channel>
<item><title>First</title><link>https://example.com/one</link></item>
<item><title>Duplicate</title><link>https://example.com/one</link></item>
</channel></rss>"""

    async def run():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, content=feed))
        async with httpx.AsyncClient(transport=transport) as client:
            return await IngestionRunner(db_session, config_path, client).run()

    report = asyncio.run(run())
    assert (report.items_fetched, report.inserted, report.duplicates, report.failures) == (2, 1, 1, 0)
    assert db_session.query(ArticleRecord).count() == 1
