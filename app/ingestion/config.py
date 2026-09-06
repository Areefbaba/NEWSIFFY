from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator

from app.ingestion.models import ContentType, SourceType


class SourceDefinition(BaseModel):
    """A source declaration loaded from the local YAML configuration."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    name: str = Field(min_length=1)
    source_type: SourceType
    url: HttpUrl
    enabled: bool = True
    trust_weight: float = Field(default=0.5, ge=0, le=1)
    query: str | None = None
    max_results: int = Field(default=20, ge=1, le=200)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    content_type: ContentType = ContentType.NEWS
    language: str = Field(default="en", min_length=1, max_length=12)

    @field_validator("name")
    @classmethod
    def name_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty or whitespace")
        return value


def load_sources(path: Path) -> list[SourceDefinition]:
    """Read and validate source declarations without contacting any source."""
    with path.open(encoding="utf-8") as source_file:
        try:
            document = yaml.safe_load(source_file)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid YAML in {path}") from error

    if not isinstance(document, dict) or not isinstance(document.get("sources"), list):
        raise ValueError("Source configuration must contain a 'sources' list")

    sources = [SourceDefinition.model_validate(value) for value in document["sources"]]
    names = [source.name.casefold() for source in sources]
    if len(names) != len(set(names)):
        raise ValueError("Source names must be unique")
    return sources
