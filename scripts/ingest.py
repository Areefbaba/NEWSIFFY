"""Run configured local ingestion sources once."""

import asyncio
import json

import httpx

from app.core.config import get_settings
from app.database.connection import SessionLocal, create_tables
from app.ingestion.runner import IngestionRunner


async def main() -> None:
    settings = get_settings()
    create_tables()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        with SessionLocal() as session:
            report = await IngestionRunner(session, settings.sources_config_path, client).run()
    print(json.dumps(report.__dict__, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
