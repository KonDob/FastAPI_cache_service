"""A failing transformer surfaces as 502 and leaves no partial state behind."""

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Payload, TransformCache
from app.services.transformer import Transformer, TransformerError, get_transformer

BODY = {"list_1": ["a", "b"], "list_2": ["c", "d"]}


def _unavailable(values: Sequence[str]) -> list[str]:
    raise TransformerError("connection refused")


def _drops_a_result(values: Sequence[str]) -> list[str]:
    return [value.upper() for value in values][:-1]


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(_unavailable, id="service-unavailable"),
        pytest.param(_drops_a_result, id="misaligned-answer"),
    ],
)
def test_transformer_failure_returns_502_and_stores_nothing(
    client: TestClient, session_factory: sessionmaker[Session], broken: Transformer
) -> None:
    app.dependency_overrides[get_transformer] = lambda: broken

    response = client.post("/payload", json=BODY)

    assert response.status_code == 502
    assert response.json() == {"detail": "Transformer service failed"}
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TransformCache)) == 0
        assert session.scalar(select(func.count()).select_from(Payload)) == 0


def test_request_succeeds_once_transformer_recovers(client: TestClient) -> None:
    app.dependency_overrides[get_transformer] = lambda: _unavailable
    assert client.post("/payload", json=BODY).status_code == 502

    del app.dependency_overrides[get_transformer]

    assert client.post("/payload", json=BODY).status_code == 201
