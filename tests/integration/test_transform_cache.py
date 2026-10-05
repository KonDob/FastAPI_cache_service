"""The transformer is called only for strings it has not transformed before."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import TransformCache
from tests.integration.fakes import CountingTransformer


def _create(client: TestClient, list_1: list[str], list_2: list[str]) -> str:
    response = client.post("/payload", json={"list_1": list_1, "list_2": list_2})
    assert response.status_code in (200, 201)
    payload_id: str = response.json()["id"]
    return payload_id


def test_new_strings_are_sent_in_one_batch(
    client: TestClient, transformer: CountingTransformer
) -> None:
    _create(client, ["a", "b"], ["c", "d"])

    assert transformer.calls == [["a", "b", "c", "d"]]


def test_repeated_payload_does_not_call_transformer(
    client: TestClient, transformer: CountingTransformer
) -> None:
    _create(client, ["a", "b"], ["c", "d"])
    transformer.calls.clear()

    _create(client, ["a", "b"], ["c", "d"])

    assert transformer.calls == []


def test_new_payload_of_known_strings_is_served_from_cache(
    client: TestClient, transformer: CountingTransformer
) -> None:
    _create(client, ["a", "b"], ["c", "d"])
    transformer.calls.clear()

    payload_id = _create(client, ["d", "c"], ["b", "a"])

    assert transformer.calls == []
    assert client.get(f"/payload/{payload_id}").json() == {"output": "D, B, C, A"}


def test_only_unseen_strings_reach_the_transformer(
    client: TestClient, transformer: CountingTransformer
) -> None:
    _create(client, ["a", "b"], ["c", "d"])
    transformer.calls.clear()

    _create(client, ["a", "new"], ["c", "other"])

    assert transformer.calls == [["new", "other"]]


def test_string_repeated_in_one_request_is_transformed_once(
    client: TestClient, transformer: CountingTransformer, session_factory: sessionmaker[Session]
) -> None:
    payload_id = _create(client, ["x", "x"], ["x", "y"])

    assert transformer.calls == [["x", "y"]]
    assert client.get(f"/payload/{payload_id}").json() == {"output": "X, X, X, Y"}
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TransformCache)) == 2
