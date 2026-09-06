from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ArticleRecord, SourceRecord
from app.ingestion.config import SourceDefinition
from app.ingestion.models import NewsItem


class SourceRepository:
    """Persistence operations for configured sources."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, source: SourceDefinition) -> SourceRecord:
        record = SourceRecord(
            id=str(uuid4()),
            name=source.name,
            source_type=source.source_type,
            url=str(source.url),
            enabled=source.enabled,
            trust_weight=source.trust_weight,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get(self, source_id: str) -> SourceRecord | None:
        return self.session.get(SourceRecord, source_id)

    def get_by_name(self, name: str) -> SourceRecord | None:
        return self.session.scalar(select(SourceRecord).where(SourceRecord.name == name))

    def list(self) -> list[SourceRecord]:
        return list(self.session.scalars(select(SourceRecord).order_by(SourceRecord.name)))

    def update(self, source_id: str, **changes: object) -> SourceRecord | None:
        record = self.get(source_id)
        if record is None:
            return None
        for field, value in changes.items():
            if hasattr(record, field):
                setattr(record, field, str(value) if field == "url" else value)
        self.session.commit()
        self.session.refresh(record)
        return record

    def upsert(self, source: SourceDefinition) -> SourceRecord:
        """Persist a configured source once, updating its mutable configuration."""
        existing = self.get_by_name(source.name)
        if existing is None:
            return self.create(source)
        updated = self.update(
            existing.id,
            source_type=source.source_type,
            url=str(source.url),
            enabled=source.enabled,
            trust_weight=source.trust_weight,
        )
        assert updated is not None
        return updated


class ArticleRepository:
    """Persistence operations for normalized articles."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item: NewsItem) -> ArticleRecord:
        return self.add_with_status(item)[0]

    def add_with_status(self, item: NewsItem) -> tuple[ArticleRecord, bool]:
        """Persist an item and report whether a new row was inserted."""
        if item.source_id is None:
            raise ValueError("source_id is required to persist an article")
        existing = self.get_by_url(str(item.url))
        if existing is not None:
            return existing, False
        values = item.model_dump(mode="python")
        values["id"] = item.id or str(uuid4())
        # Source identity is represented by the relationship, not duplicated text columns.
        values.pop("source_name")
        values.pop("source_type")
        values["url"] = str(item.url)
        values["canonical_url"] = str(item.canonical_url) if item.canonical_url else None
        values["authors_json"] = values.pop("authors")
        values["metadata_json"] = values.pop("metadata")
        record = ArticleRecord(**values)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record, True

    def get(self, item_id: str) -> ArticleRecord | None:
        return self.session.get(ArticleRecord, item_id)

    def get_by_url(self, url: str) -> ArticleRecord | None:
        return self.session.scalar(select(ArticleRecord).where(ArticleRecord.url == url))

    def update(self, item_id: str, **changes: object) -> ArticleRecord | None:
        record = self.get(item_id)
        if record is None:
            return None
        for field, value in changes.items():
            if hasattr(record, field):
                setattr(record, field, value)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list(self, limit: int = 50) -> list[ArticleRecord]:
        statement = select(ArticleRecord).order_by(ArticleRecord.fetched_at.desc()).limit(limit)
        return list(self.session.scalars(statement))


NewsRepository = ArticleRepository
