import logging
from xml.etree import ElementTree as ET

import httpx

from app.ingestion.base import SourceConnector
from app.ingestion.config import SourceDefinition
from app.ingestion.errors import MalformedContentError
from app.ingestion.http import fetch_bytes
from app.ingestion.models import NewsItem, SourceType
from app.ingestion.normalize import clean_text, make_news_item, parse_timestamp


logger = logging.getLogger(__name__)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, names: set[str]) -> str | None:
    for child in element:
        if local_name(child.tag) in names:
            return child.text
    return None


class RSSConnector(SourceConnector):
    """Generic RSS/Atom connector that normalizes each valid feed entry."""

    def __init__(self, source: SourceDefinition, client: httpx.AsyncClient, retry_attempts: int = 3) -> None:
        self.source = source
        self.client = client
        self.retry_attempts = retry_attempts

    async def fetch(self) -> list[NewsItem]:
        payload = await fetch_bytes(
            self.client,
            str(self.source.url),
            timeout_seconds=self.source.timeout_seconds,
            retry_attempts=self.retry_attempts,
        )
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as error:
            raise MalformedContentError(f"Malformed feed XML from {self.source.name}") from error

        root_name = local_name(root.tag)
        if root_name == "feed":
            return self._parse_atom(root)
        if root_name in {"rss", "RDF"}:
            return self._parse_rss(root)
        raise MalformedContentError(f"Response from {self.source.name} is not an RSS or Atom feed")

    def _parse_rss(self, root: ET.Element) -> list[NewsItem]:
        channel = next((element for element in root.iter() if local_name(element.tag) == "channel"), root)
        feed_title = clean_text(child_text(channel, {"title"}))
        items: list[NewsItem] = []
        for entry in (element for element in channel if local_name(element.tag) == "item"):
            try:
                authors = [value for value in [child_text(entry, {"author", "creator"})] if value]
                item = make_news_item(
                    source_name=self.source.name,
                    source_type=SourceType.RSS,
                    content_type=self.source.content_type,
                    title=child_text(entry, {"title"}),
                    url=child_text(entry, {"link"}),
                    authors=authors,
                    published_at=parse_timestamp(child_text(entry, {"pubDate", "date", "published"})),
                    summary=child_text(entry, {"description", "encoded", "summary"}),
                    language=self.source.language,
                    metadata={"feed_title": feed_title, "feed_url": str(self.source.url)},
                )
                if item is not None:
                    items.append(item)
                else:
                    logger.warning("Skipping malformed RSS entry from %s", self.source.name)
            except (TypeError, ValueError) as error:
                logger.warning("Skipping invalid RSS entry from %s: %s", self.source.name, error)
        return items

    def _parse_atom(self, root: ET.Element) -> list[NewsItem]:
        feed_title = clean_text(child_text(root, {"title"}))
        items: list[NewsItem] = []
        for entry in (element for element in root if local_name(element.tag) == "entry"):
            try:
                links = [child for child in entry if local_name(child.tag) == "link"]
                preferred_link = next(
                    (link for link in links if link.attrib.get("href") and link.attrib.get("rel", "alternate") == "alternate"),
                    None,
                )
                link = preferred_link.attrib.get("href") if preferred_link is not None else next(
                    (element.attrib.get("href") for element in links if element.attrib.get("href")), None
                )
                authors = [child_text(author, {"name"}) or "" for author in entry if local_name(author.tag) == "author"]
                item = make_news_item(
                    source_name=self.source.name,
                    source_type=SourceType.RSS,
                    content_type=self.source.content_type,
                    title=child_text(entry, {"title"}),
                    url=link,
                    authors=authors,
                    published_at=parse_timestamp(child_text(entry, {"published", "updated"})),
                    summary=child_text(entry, {"summary", "content"}),
                    language=self.source.language,
                    metadata={"feed_title": feed_title, "feed_url": str(self.source.url)},
                )
                if item is not None:
                    items.append(item)
                else:
                    logger.warning("Skipping malformed Atom entry from %s", self.source.name)
            except (TypeError, ValueError) as error:
                logger.warning("Skipping invalid Atom entry from %s: %s", self.source.name, error)
        return items
