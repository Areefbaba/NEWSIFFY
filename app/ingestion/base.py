from abc import ABC, abstractmethod

from app.ingestion.models import NewsItem


class SourceConnector(ABC):
    """Minimal contract all source-specific collectors must implement."""

    @abstractmethod
    async def fetch(self) -> list[NewsItem]:
        """Fetch and normalize items from one configured source."""
        raise NotImplementedError
