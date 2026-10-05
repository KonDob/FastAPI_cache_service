"""HTTP contract of the payload endpoints."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

SAMPLE_REQUEST = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
SAMPLE_OUTPUT = (
    "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
)


def test_create_returns_201_with_new_id(client: TestClient) -> None:
    response = client.post("/payload", json=SAMPLE_REQUEST)

    assert response.status_code == 201
    assert response.json()["message"] == "Payload created"


def test_read_returns_sample_output_from_task(client: TestClient) -> None:
    payload_id = client.post("/payload", json=SAMPLE_REQUEST).json()["id"]

    response = client.get(f"/payload/{payload_id}")

    assert response.status_code == 200
    assert response.json() == {"output": SAMPLE_OUTPUT}


def test_repeated_create_returns_200_with_same_id(client: TestClient) -> None:
    first = client.post("/payload", json=SAMPLE_REQUEST)
    second = client.post("/payload", json=SAMPLE_REQUEST)

    assert second.status_code == 200
    assert second.json() == {"id": first.json()["id"], "message": "Payload already exists"}


def test_reordered_input_is_a_different_payload(client: TestClient) -> None:
    reordered = {"list_1": SAMPLE_REQUEST["list_2"], "list_2": SAMPLE_REQUEST["list_1"]}

    first = client.post("/payload", json=SAMPLE_REQUEST)
    second = client.post("/payload", json=reordered)

    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]


def test_read_unknown_id_returns_404(client: TestClient) -> None:
    response = client.get(f"/payload/{uuid4()}")

    assert response.status_code == 404


def test_read_malformed_id_returns_422(client: TestClient) -> None:
    response = client.get("/payload/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"list_1": ["a"]}, id="missing-list"),
        pytest.param({"list_1": [], "list_2": []}, id="empty-lists"),
        pytest.param({"list_1": ["a"], "list_2": ["b", "c"]}, id="different-lengths"),
        pytest.param({"list_1": ["a" * 1001], "list_2": ["b"]}, id="string-too-long"),
        pytest.param({"list_1": ["a"] * 1001, "list_2": ["b"] * 1001}, id="too-many-items"),
        pytest.param({"list_1": [1], "list_2": ["b"]}, id="not-a-string"),
    ],
)
def test_create_rejects_invalid_input(client: TestClient, body: dict[str, Any]) -> None:
    response = client.post("/payload", json=body)

    assert response.status_code == 422


def test_create_accepts_input_at_the_limits(client: TestClient) -> None:
    body = {"list_1": ["a" * 1000] * 1000, "list_2": ["b" * 1000] * 1000}

    response = client.post("/payload", json=body)

    assert response.status_code == 201
