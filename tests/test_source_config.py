from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.config import load_sources


def write_yaml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_valid_yaml_and_preserves_disabled_source(tmp_path: Path) -> None:
    path = write_yaml(tmp_path / "sources.yaml", """sources:
  - name: Example feed
    source_type: rss
    url: https://example.com/feed.xml
    enabled: false
    trust_weight: 0.8
""")
    sources = load_sources(path)
    assert len(sources) == 1
    assert sources[0].enabled is False
    assert sources[0].trust_weight == 0.8


def test_missing_yaml_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_sources(tmp_path / "missing.yaml")


def test_malformed_yaml_is_reported(tmp_path: Path) -> None:
    path = write_yaml(tmp_path / "sources.yaml", "sources: [name: broken")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_sources(path)


@pytest.mark.parametrize("content", [
    "sources:\n  - source_type: rss\n    url: https://example.com",
    "sources:\n  - name: Example\n    url: https://example.com",
    "sources:\n  - name: Example\n    source_type: rss",
    "sources:\n  - name: Example\n    source_type: newsletter\n    url: https://example.com",
    "sources:\n  - name: Example\n    source_type: rss\n    url: https://example.com\n    trust_weight: -0.1",
    "sources:\n  - name: Example\n    source_type: rss\n    url: https://example.com\n    trust_weight: 1.1",
    "sources:\n  - name: Example\n    source_type: rss\n    url: https://example.com\n    trust_weight: high",
])
def test_invalid_source_definitions_are_rejected(tmp_path: Path, content: str) -> None:
    with pytest.raises(ValidationError):
        load_sources(write_yaml(tmp_path / "sources.yaml", content))


def test_duplicate_source_names_are_rejected(tmp_path: Path) -> None:
    path = write_yaml(tmp_path / "sources.yaml", """sources:
  - name: Example
    source_type: rss
    url: https://example.com/one
  - name: example
    source_type: api
    url: https://example.com/two
""")
    with pytest.raises(ValueError, match="unique"):
        load_sources(path)
