from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.ingestion.models import ContentType, NewsItem, SourceType


def item_payload() -> dict[str, object]:
    return {
        "source_name": "Example AI",
        "source_type": SourceType.RSS,
        "content_type": ContentType.NEWS,
        "title": "A useful update",
        "url": "https://example.com/article",
        "fetched_at": datetime.now(UTC),
        "metadata": {"topic": "ai"},
    }


def test_valid_news_item_and_optional_fields() -> None:
    item = NewsItem(**item_payload(), source_id="source-1", published_at=None, summary=None, content=None)
    assert item.source_id == "source-1"
    assert item.authors == []
    assert item.published_at is None


@pytest.mark.parametrize("field", ["source_name", "source_type", "content_type", "title", "url"])
def test_required_fields_are_enforced(field: str) -> None:
    payload = item_payload()
    payload.pop(field)
    with pytest.raises(ValidationError):
        NewsItem(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_type", "newsletter"),
        ("content_type", "video"),
        ("title", ""),
        ("title", "   \t"),
        ("url", "not a URL"),
        ("authors", "Ada Lovelace"),
        ("authors", [""]),
        ("metadata", ["not", "a", "mapping"]),
    ],
)
def test_invalid_news_item_values_are_rejected(field: str, value: object) -> None:
    payload = item_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        NewsItem(**payload)


def test_fetched_at_is_required_but_published_at_is_optional() -> None:
    payload = item_payload()
    payload.pop("fetched_at")
    with pytest.raises(ValidationError):
        NewsItem(**payload)
    assert NewsItem(**item_payload()).published_at is None


def test_unicode_emoji_and_large_content_are_preserved() -> None:
    content = "人工知能の進展 🤖 " + ("x" * 1_048_576)
    payload = item_payload()
    payload["title"] = "研究速報 🚀"
    payload["content"] = content
    payload["authors"] = []
    item = NewsItem(**payload)
    assert item.title == "研究速報 🚀"
    assert item.content == content
