"""Health probe used by the container healthcheck."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.main import app


def test_health_is_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_503_when_database_is_unreachable(client: TestClient) -> None:
    # Port 9 (discard) has no listener on a normal machine, so the connection is refused.
    unreachable = create_engine("postgresql+psycopg://user:pass@127.0.0.1:9/db")

    def get_unreachable_session() -> Iterator[Session]:
        with Session(unreachable) as session:
            yield session

    app.dependency_overrides[get_session] = get_unreachable_session

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unreachable"}
