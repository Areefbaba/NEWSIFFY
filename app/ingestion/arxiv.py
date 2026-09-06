import logging
from xml.etree import ElementTree as ET

import httpx

from app.ingestion.base import SourceConnector
from app.ingestion.config import SourceDefinition
from app.ingestion.errors import MalformedContentError
from app.ingestion.http import fetch_bytes
from app.ingestion.models import ContentType, NewsItem, SourceType
from app.ingestion.normalize import clean_text, make_news_item, parse_timestamp
from app.ingestion.rss import child_text, local_name


logger = logging.getLogger(__name__)


class ArxivConnector(SourceConnector):
    """Connector for the arXiv Atom export API."""

    def __init__(self, source: SourceDefinition, client: httpx.AsyncClient, retry_attempts: int = 3) -> None:
        self.source = source
        self.client = client
        self.retry_attempts = retry_attempts

    async def fetch(self) -> list[NewsItem]:
        params: dict[str, str | int] = {"start": 0, "max_results": self.source.max_results}
        if self.source.query:
            params["search_query"] = self.source.query
        payload = await fetch_bytes(
            self.client,
            str(self.source.url),
            params=params,
            timeout_seconds=self.source.timeout_seconds,
            retry_attempts=self.retry_attempts,
        )
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as error:
            raise MalformedContentError(f"Malformed arXiv response from {self.source.name}") from error
        if local_name(root.tag) != "feed":
            raise MalformedContentError("arXiv response is not an Atom feed")

        items: list[NewsItem] = []
        for entry in (element for element in root if local_name(element.tag) == "entry"):
            try:
                source_url = clean_text(child_text(entry, {"id"}))
                arxiv_id = source_url.rsplit("/", 1)[-1] if source_url else None
                links = [child for child in entry if local_name(child.tag) == "link"]
                pdf_url = next((link.attrib.get("href") for link in links if link.attrib.get("title") == "pdf"), None)
                categories = [category.attrib["term"] for category in entry if local_name(category.tag) == "category" and "term" in category.attrib]
                authors = [child_text(author, {"name"}) or "" for author in entry if local_name(author.tag) == "author"]
                updated = parse_timestamp(child_text(entry, {"updated"}))
                item = make_news_item(
                    source_name=self.source.name,
                    source_type=SourceType.ARXIV,
                    content_type=ContentType.PAPER,
                    title=child_text(entry, {"title"}),
                    url=source_url,
                    canonical_url=source_url,
                    authors=authors,
                    published_at=parse_timestamp(child_text(entry, {"published"})),
                    summary=child_text(entry, {"summary"}),
                    language=self.source.language,
                    metadata={
                        "arxiv_id": arxiv_id,
                        "pdf_url": pdf_url,
                        "source_url": source_url,
                        "categories": categories,
                        "updated_at": updated.isoformat() if updated else None,
                    },
                )
                if item is not None:
                    items.append(item)
                else:
                    logger.warning("Skipping malformed arXiv entry from %s", self.source.name)
            except (TypeError, ValueError) as error:
                logger.warning("Skipping invalid arXiv entry from %s: %s", self.source.name, error)
        return items
