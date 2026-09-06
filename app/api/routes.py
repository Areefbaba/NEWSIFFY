from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database.connection import get_session
from app.database.repository import ArticleRepository, SourceRepository
from app.ingestion.config import SourceDefinition
from app.ingestion.models import NewsItem

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_session)]


class NewsItemResponse(NewsItem):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    @classmethod
    def from_record(cls, record: object) -> "NewsItemResponse":
        data = {
            "id": record.id,
            "source_id": record.source_id,
            "source_name": record.source.name,
            "source_type": record.source.source_type,
            "content_type": record.content_type,
            "title": record.title,
            "url": record.url,
            "canonical_url": record.canonical_url,
            "authors": record.authors_json,
            "published_at": record.published_at,
            "fetched_at": record.fetched_at,
            "summary": record.summary,
            "content": record.content,
            "language": record.language,
            "metadata": record.metadata_json,
            "raw_hash": record.raw_hash,
        }
        return cls.model_validate(data)


class HealthResponse(BaseModel):
    status: str
    service: str


class SourceResponse(SourceDefinition):
    id: str


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="newsify")


@router.post("/items", response_model=NewsItemResponse, status_code=status.HTTP_201_CREATED, tags=["items"])
def create_item(item: NewsItem, session: SessionDependency) -> NewsItemResponse:
    if item.source_id is None or SourceRepository(session).get(item.source_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A valid source_id is required")
    record = ArticleRepository(session).add(item)
    return NewsItemResponse.from_record(record)


@router.get("/items", response_model=list[NewsItemResponse], tags=["items"])
def list_items(session: SessionDependency, limit: Annotated[int, Query(ge=1, le=100)] = 50) -> list[NewsItemResponse]:
    return [NewsItemResponse.from_record(record) for record in ArticleRepository(session).list(limit)]


@router.get("/items/{item_id}", response_model=NewsItemResponse, tags=["items"])
def get_item(item_id: str, session: SessionDependency) -> NewsItemResponse:
    record = ArticleRepository(session).get(item_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return NewsItemResponse.from_record(record)


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED, tags=["sources"])
def create_source(source: SourceDefinition, session: SessionDependency) -> SourceResponse:
    return SourceResponse.model_validate(SourceRepository(session).create(source), from_attributes=True)


public_router = APIRouter()


@public_router.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "newsify", "status": "ok"}


@public_router.get("/health", response_model=HealthResponse, tags=["system"])
def public_health() -> HealthResponse:
    return health()


@public_router.get("/api/sources", response_model=list[SourceResponse], tags=["sources"])
def list_sources(session: SessionDependency) -> list[SourceResponse]:
    return [SourceResponse.model_validate(record, from_attributes=True) for record in SourceRepository(session).list()]
