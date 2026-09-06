import asyncio

import httpx
import pytest

from app.ingestion.arxiv import ArxivConnector
from app.ingestion.config import SourceDefinition
from app.ingestion.errors import FetchError, MalformedContentError
from app.database.repository import ArticleRepository, SourceRepository


ARXIV_FEED = b"""<feed xmlns='http://www.w3.org/2005/Atom'>
<entry><id>http://arxiv.org/abs/2401.00001v2</id><title> First AI paper </title><published>2024-01-02T00:00:00Z</published><updated>2024-01-03T00:00:00Z</updated><summary> Abstract text </summary><author><name>Ada</name></author><category term='cs.AI'/><link title='pdf' href='https://arxiv.org/pdf/2401.00001v2'/></entry>
<entry><id>http://arxiv.org/abs/2401.00002</id><title>Second paper</title><author><name>Grace</name></author></entry>
</feed>"""


def source() -> SourceDefinition:
    return SourceDefinition(name="arXiv AI", source_type="arxiv", url="https://export.arxiv.org/api/query", query="cat:cs.AI", max_results=2)


def fetch_payload(payload: bytes) -> tuple[list, httpx.URL]:
    seen_url: httpx.URL | None = None

    async def run() -> list:
        nonlocal seen_url
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal seen_url
            seen_url = request.url
            return httpx.Response(200, content=payload)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ArxivConnector(source(), client).fetch()
    items = asyncio.run(run())
    assert seen_url is not None
    return items, seen_url


def test_arxiv_extracts_papers_and_request_configuration() -> None:
    items, request_url = fetch_payload(ARXIV_FEED)
    assert len(items) == 2
    assert request_url.params["search_query"] == "cat:cs.AI"
    assert request_url.params["max_results"] == "2"
    assert items[0].content_type == "paper"
    assert items[0].metadata["arxiv_id"] == "2401.00001v2"
    assert items[0].metadata["pdf_url"] == "https://arxiv.org/pdf/2401.00001v2"
    assert items[0].metadata["categories"] == ["cs.AI"]
    assert items[0].summary == "Abstract text"
    assert items[1].published_at is None
    assert items[1].metadata["pdf_url"] is None


def test_malformed_arxiv_response_is_reported() -> None:
    with pytest.raises(MalformedContentError):
        fetch_payload(b"<feed><entry>")


@pytest.mark.parametrize("status", [400, 404, 429, 500])
def test_arxiv_http_errors_are_reported(status: int) -> None:
    async def run() -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(status))
        async with httpx.AsyncClient(transport=transport) as client:
            await ArxivConnector(source(), client, retry_attempts=1).fetch()
    with pytest.raises(FetchError):
        asyncio.run(run())


def test_duplicate_arxiv_paper_is_idempotent(db_session) -> None:
    source_record = SourceRepository(db_session).create(source())
    paper, _ = fetch_payload(ARXIV_FEED)
    repository = ArticleRepository(db_session)
    first, first_inserted = repository.add_with_status(paper[0].model_copy(update={"source_id": source_record.id}))
    second, second_inserted = repository.add_with_status(paper[0].model_copy(update={"source_id": source_record.id}))
    assert first.id == second.id
    assert (first_inserted, second_inserted) == (True, False)


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("timeout"), httpx.ConnectError("offline")])
def test_timeout_and_connection_errors_are_reported(failure: Exception) -> None:
    async def run() -> None:
        transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(failure))
        async with httpx.AsyncClient(transport=transport) as client:
            await ArxivConnector(source(), client, retry_attempts=1).fetch()
    with pytest.raises(FetchError):
        asyncio.run(run())
