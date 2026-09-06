from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    application = create_app(f"sqlite:///{tmp_path / 'api-test.db'}")
    with TestClient(application) as test_client:
        yield test_client


def source_payload() -> dict[str, object]:
    return {"name": "API Source", "source_type": "rss", "url": "https://example.com/feed", "trust_weight": 0.7}


def item_payload(source_id: str) -> dict[str, object]:
    return {
        "source_id": source_id, "source_name": "API Source", "source_type": "rss", "content_type": "news",
        "title": "API item 🤖", "url": "https://example.com/api-item", "fetched_at": datetime.now(UTC).isoformat(),
        "metadata": {"test": True},
    }


def test_system_and_sources_endpoints(client: TestClient) -> None:
    assert client.get("/").json() == {"service": "newsify", "status": "ok"}
    assert client.get("/health").json() == {"status": "ok", "service": "newsify"}
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/sources").json() == []
    created = client.post("/api/v1/sources", json=source_payload())
    assert created.status_code == 201
    assert client.get("/api/sources").json()[0]["name"] == "API Source"


def test_item_create_list_get_and_invalid_source(client: TestClient) -> None:
    source = client.post("/api/v1/sources", json=source_payload()).json()
    assert client.post("/api/v1/items", json=item_payload("does-not-exist")).status_code == 422
    response = client.post("/api/v1/items", json=item_payload(source["id"]))
    assert response.status_code == 201
    created = response.json()
    assert created["source_id"] == source["id"]
    assert client.get("/api/v1/items").json()[0]["id"] == created["id"]
    assert client.get(f"/api/v1/items/{created['id']}").json()["title"] == "API item 🤖"
    assert client.get("/api/v1/items/missing").status_code == 404
