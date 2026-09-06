from collections.abc import Generator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import public_router, router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.connection import create_database_engine, create_tables, get_session
from sqlalchemy.orm import Session, sessionmaker


def create_app(database_url: str | None = None) -> FastAPI:
    """Create the application; tests may supply an isolated SQLite URL."""
    settings = get_settings()
    database_engine = create_database_engine(database_url) if database_url else None
    local_session_factory = sessionmaker(bind=database_engine, autoflush=False, autocommit=False) if database_engine else None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configure_logging()
        create_tables(database_engine)
        yield

    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    if local_session_factory is not None:
        def isolated_session() -> Generator[Session, None, None]:
            session = local_session_factory()
            try:
                yield session
            finally:
                session.close()

        application.dependency_overrides[get_session] = isolated_session
    application.include_router(public_router)
    application.include_router(router, prefix="/api/v1")
    return application


app = create_app()
