# Newsify

Newsify is a local-first foundation for collecting and organizing AI news, papers,
releases, benchmarks, open-source projects, company updates, and policy coverage.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive documentation at
`/docs`. Health is exposed at `GET /api/v1/health`.

## Current scope

- Normalized `NewsItem` and source/content enums
- Async source-connector contract
- SQLite storage with `sources`, `articles`, `events`, `event_articles`, and `papers`
- `articles.source_id` foreign-key relationship; source name/type remain ingestion context only
- Source and article repositories with URL-based idempotent article insertion
- Health, source list/create, and item create/read API endpoints
- Validated declarative source configuration

Connectors, enrichment, intelligence, retrieval, and delivery are deliberately
reserved for future milestones.

## Ingestion

The Day-2 runner loads enabled sources from `config/sources.yaml`, chooses the
RSS/Atom or arXiv connector, normalizes valid entries, and stores them through
the article repository. Configure `url`, `query` (arXiv), `max_results`,
`timeout_seconds`, `content_type` (RSS), and `language` in YAML; no source URL
is embedded in application code. Run one local ingestion pass with:

```powershell
python -m scripts.ingest
```

The command prints sources processed, fetched/inserted/duplicate item counts,
failures, duration, and any reported errors. HTTP timeouts, connection errors,
429s, and 5xx responses receive bounded local retries; other 4xx and malformed
responses are reported without retrying.

## Day-1 limitations

Events and papers have persistence schemas but no clustering or enrichment workflow.
The ingestion engine supports RSS/Atom and arXiv only; no crawler, LLM, embedding,
retrieval, or delivery feature is implemented. API item creation requires a
pre-existing `source_id`; create sources first through `POST /api/v1/sources` or
populate them from validated local YAML.
