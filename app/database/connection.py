from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_options(database_url: str) -> dict[str, object]:
    return {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {}


def create_database_engine(database_url: str) -> Engine:
    """Create a SQLite-aware engine with foreign-key enforcement enabled."""
    database_engine = create_engine(database_url, **_engine_options(database_url))
    if database_url.startswith("sqlite"):
        @event.listens_for(database_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return database_engine


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_tables(database_engine: Engine | None = None) -> None:
    from app.database import models  # noqa: F401 - register table metadata

    Base.metadata.create_all(bind=database_engine or engine)
