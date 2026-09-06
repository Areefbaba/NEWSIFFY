from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SourceType(StrEnum):
    RSS = "rss"
    API = "api"
    WEB = "web"
    ARXIV = "arxiv"
    GITHUB = "github"


class ContentType(StrEnum):
    NEWS = "news"
    PAPER = "paper"
    MODEL_RELEASE = "model_release"
    TOOL_RELEASE = "tool_release"
    BENCHMARK = "benchmark"
    COMPANY_UPDATE = "company_update"
    POLICY = "policy"
    OPEN_SOURCE = "open_source"


class NewsItem(BaseModel):
    """Source-independent representation of an item collected from the web."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    id: str | None = None
    source_id: str | None = None
    source_name: str
    source_type: SourceType
    content_type: ContentType
    title: str = Field(min_length=1)
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    fetched_at: datetime
    summary: str | None = None
    content: str | None = None
    language: str = "en"
    metadata: dict[str, object] = Field(default_factory=dict)
    raw_hash: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty or whitespace")
        return value

    @field_validator("authors")
    @classmethod
    def authors_must_contain_names(cls, value: list[str]) -> list[str]:
        if any(not author.strip() for author in value):
            raise ValueError("authors must not contain blank names")
        return value
