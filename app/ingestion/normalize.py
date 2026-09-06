from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from app.ingestion.models import ContentType, NewsItem, SourceType


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def normalize_url(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    parsed = urlsplit(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


def parse_timestamp(value: str | None) -> datetime | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def normalize_authors(authors: list[str]) -> list[str]:
    normalized: list[str] = []
    for author in authors:
        name = clean_text(author)
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def make_news_item(
    *,
    source_name: str,
    source_type: SourceType,
    content_type: ContentType,
    title: str | None,
    url: str | None,
    authors: list[str] | None = None,
    published_at: datetime | None = None,
    summary: str | None = None,
    content: str | None = None,
    language: str = "en",
    metadata: dict[str, object] | None = None,
    canonical_url: str | None = None,
) -> NewsItem | None:
    """Create a valid normalized item, or skip an entry lacking identity fields."""
    normalized_title = clean_text(title)
    normalized_url = normalize_url(url)
    if normalized_title is None or normalized_url is None:
        return None
    return NewsItem(
        source_name=source_name,
        source_type=source_type,
        content_type=content_type,
        title=normalized_title,
        url=normalized_url,
        canonical_url=normalize_url(canonical_url),
        authors=normalize_authors(authors or []),
        published_at=published_at,
        fetched_at=datetime.now(UTC),
        summary=clean_text(summary),
        content=clean_text(content),
        language=language,
        metadata=metadata or {},
    )
