"""Integration fixtures: a dedicated PostgreSQL database and a counting transformer.

Tests run against real PostgreSQL rather than SQLite because the service relies on
PostgreSQL behaviour (ON CONFLICT, unique constraints under concurrency).
"""

import os
from collections.abc import Iterator, Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.services.transformer import get_transformer, upper_case_transformer

TEST_DATABASE_NAME = "cache_test"


class CountingTransformer:
    """Real transformation plus a record of every call, to assert on cache behaviour."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, values: Sequence[str]) -> list[str]:
        self.calls.append(list(values))
        return upper_case_transformer(values)


def _test_database_url() -> URL:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return make_url(explicit)
    # Same server as development, separate database: tests never touch development data.
    return make_url(Settings().database_url).set(database=TEST_DATABASE_NAME)


def _create_database_if_missing(url: URL) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as error:
        pytest.exit(
            f"PostgreSQL is not reachable at {url.render_as_string(hide_password=True)}; "
            f"start it with `docker compose up -d --wait`.\n{error}",
            returncode=1,
        )
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _test_database_url()
    _create_database_if_missing(url)
    engine = create_engine(url)
    # Recreate rather than reuse: the schema has no migrations and may have changed.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables}"))
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@pytest.fixture
def client(
    session_factory: sessionmaker[Session], transformer: CountingTransformer
) -> Iterator[TestClient]:
    def get_test_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_transformer] = lambda: transformer
    # Not used as a context manager on purpose: the lifespan would create tables through
    # the application's own engine, i.e. in the development database.
    yield TestClient(app)
    app.dependency_overrides.clear()
