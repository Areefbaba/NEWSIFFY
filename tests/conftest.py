from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.database.connection import create_database_engine, create_tables


@pytest.fixture
def database_engine(tmp_path) -> Generator[Engine, None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'newsify-test.db'}")
    create_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(database_engine: Engine) -> Generator[Session, None, None]:
    with Session(database_engine) as session:
        yield session
