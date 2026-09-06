from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import ArticleRecord
from app.database.repository import ArticleRepository, SourceRepository
from app.ingestion.config import SourceDefinition
from app.ingestion.models import ContentType, NewsItem, SourceType


def source_definition() -> SourceDefinition:
    return SourceDefinition(name="Example", source_type="rss", url="https://example.com/feed")


def item(source_id: str, url: str = "https://example.com/news", title: str = "A local-first future") -> NewsItem:
    return NewsItem(
        source_id=source_id,
        source_name="Example",
        source_type=SourceType.RSS,
        content_type=ContentType.NEWS,
        title=title,
        url=url,
        fetched_at=datetime.now(UTC),
        metadata={"category": "ai"},
    )


def test_database_initialization_creates_expected_tables(database_engine) -> None:
    expected = {"sources", "articles", "events", "event_articles", "papers"}
    assert expected <= set(inspect(database_engine).get_table_names())
    unique_constraints = inspect(database_engine).get_unique_constraints("articles")
    assert any(constraint["column_names"] == ["url"] for constraint in unique_constraints)


def test_source_crud_and_article_retrieval(db_session: Session) -> None:
    sources = SourceRepository(db_session)
    source = sources.create(source_definition())
    updated = sources.update(source.id, enabled=False, trust_weight=0.9)
    saved = ArticleRepository(db_session).add(item(source.id))
    found = ArticleRepository(db_session).get(saved.id)

    assert updated is not None and updated.enabled is False
    assert found is not None
    assert found.title == "A local-first future"
    assert found.source_id == source.id
    assert found.metadata_json == {"category": "ai"}


def test_article_update_and_recent_ordering(db_session: Session) -> None:
    source = SourceRepository(db_session).create(source_definition())
    repository = ArticleRepository(db_session)
    older = item(source.id, "https://example.com/older")
    newer = item(source.id, "https://example.com/newer")
    older.fetched_at = datetime(2025, 1, 1, tzinfo=UTC)
    newer.fetched_at = datetime(2025, 1, 2, tzinfo=UTC)
    first = repository.add(older)
    repository.add(newer)
    updated = repository.update(first.id, title="Updated title")

    assert updated is not None and updated.title == "Updated title"
    assert [record.url for record in repository.list()] == ["https://example.com/newer", "https://example.com/older"]
    assert repository.get("does-not-exist") is None


def test_duplicate_url_is_idempotent_but_distinct_urls_remain_distinct(db_session: Session) -> None:
    source = SourceRepository(db_session).create(source_definition())
    repository = ArticleRepository(db_session)
    first = repository.add(item(source.id))
    repeated = repository.add(item(source.id, title="Same URL, new fetch"))
    second = repository.add(item(source.id, "https://example.com/another-report"))

    assert first.id == repeated.id
    assert second.id != first.id
    assert len(list(db_session.scalars(select(ArticleRecord)))) == 2


def test_foreign_keys_reject_a_nonexistent_source(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        ArticleRepository(db_session).add(item("missing-source"))
    db_session.rollback()
