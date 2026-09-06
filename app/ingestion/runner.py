import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import httpx
from sqlalchemy.orm import Session

from app.database.repository import ArticleRepository, SourceRepository
from app.ingestion.arxiv import ArxivConnector
from app.ingestion.base import SourceConnector
from app.ingestion.config import SourceDefinition, load_sources
from app.ingestion.rss import RSSConnector


logger = logging.getLogger(__name__)


@dataclass
class IngestionReport:
    sources_processed: int = 0
    items_fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    failures: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


def connector_for(source: SourceDefinition, client: httpx.AsyncClient) -> SourceConnector:
    if source.source_type == "rss":
        return RSSConnector(source, client)
    if source.source_type == "arxiv":
        return ArxivConnector(source, client)
    raise ValueError(f"No ingestion connector is available for source type '{source.source_type}'")


class IngestionRunner:
    """Small local orchestration layer for configured source ingestion."""

    def __init__(self, session: Session, config_path: Path, client: httpx.AsyncClient) -> None:
        self.session = session
        self.config_path = config_path
        self.client = client

    async def run(self) -> IngestionReport:
        started_at = monotonic()
        report = IngestionReport()
        source_repository = SourceRepository(self.session)
        article_repository = ArticleRepository(self.session)

        try:
            configured_sources = load_sources(self.config_path)
        except (OSError, ValueError) as error:
            report.failures = 1
            report.errors.append(f"Configuration error: {error}")
            report.duration_seconds = monotonic() - started_at
            return report

        for definition in configured_sources:
            if not definition.enabled:
                continue
            report.sources_processed += 1
            try:
                source = source_repository.upsert(definition)
                connector = connector_for(definition, self.client)
                items = await connector.fetch()
                report.items_fetched += len(items)
                for item in items:
                    try:
                        _, inserted = article_repository.add_with_status(item.model_copy(update={"source_id": source.id}))
                        if inserted:
                            report.inserted += 1
                        else:
                            report.duplicates += 1
                    except Exception as error:  # continue after one unusable entry
                        self.session.rollback()
                        report.failures += 1
                        message = f"Item from {definition.name} could not be persisted: {error}"
                        report.errors.append(message)
                        logger.warning(message)
                source_repository.update(source.id, last_fetched_at=datetime.now(UTC))
            except Exception as error:  # one source must not block the remaining sources
                self.session.rollback()
                report.failures += 1
                message = f"Source {definition.name} failed: {error}"
                report.errors.append(message)
                logger.warning(message)

        report.duration_seconds = monotonic() - started_at
        return report
