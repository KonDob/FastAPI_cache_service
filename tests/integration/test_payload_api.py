"""HTTP contract of the payload endpoints."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.integration.fakes import CountingTransformer

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
    body = response.json()
    assert body == {"id": body["id"], "message": "Payload created"}
    assert UUID(body["id"]).version == 4


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
    ("body", "loc", "error_type"),
    [
        pytest.param({"list_1": ["a"]}, ["body", "list_2"], "missing", id="missing-list"),
        pytest.param(
            {"list_1": [], "list_2": []}, ["body", "list_1"], "too_short", id="empty-lists"
        ),
        pytest.param(
            {"list_1": ["a"], "list_2": ["b", "c"]}, ["body"], "value_error", id="different-lengths"
        ),
        pytest.param(
            {"list_1": ["a" * 1001], "list_2": ["b"]},
            ["body", "list_1", 0],
            "string_too_long",
            id="string-too-long",
        ),
        pytest.param(
            {"list_1": ["a"] * 1001, "list_2": ["b"] * 1001},
            ["body", "list_1"],
            "too_long",
            id="too-many-items",
        ),
        pytest.param(
            {"list_1": [1], "list_2": ["b"]},
            ["body", "list_1", 0],
            "string_type",
            id="not-a-string",
        ),
        pytest.param(
            {"list_1": ["a\x00b"], "list_2": ["c"]},
            ["body", "list_1", 0],
            "value_error",
            id="nul-character",
        ),
    ],
)
def test_create_rejects_invalid_input(
    client: TestClient, body: dict[str, Any], loc: list[str | int], error_type: str
) -> None:
    response = client.post("/payload", json=body)

    assert response.status_code == 422
    # Checking where and why guards against a 422 raised for an unrelated reason.
    errors = [(error["loc"], error["type"]) for error in response.json()["detail"]]
    assert (loc, error_type) in errors


def test_create_rejects_lone_surrogate_with_422(client: TestClient) -> None:
    # Valid JSON, but not encodable as UTF-8: the error body must still be renderable.
    body = '{"list_1": ["lone \\ud800"], "list_2": ["b"]}'

    response = client.post("/payload", content=body, headers={"content-type": "application/json"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "list_1", 0]


def test_create_accepts_input_at_the_limits(
    client: TestClient, transformer: CountingTransformer
) -> None:
    # All strings distinct: the worst case for the single cache INSERT of one request.
    def max_length_strings(prefix: str) -> list[str]:
        return [f"{prefix}{i:04}".ljust(1000, "x") for i in range(1000)]

    body = {"list_1": max_length_strings("a"), "list_2": max_length_strings("b")}

    response = client.post("/payload", json=body)

    assert response.status_code == 201
    assert len(transformer.calls[0]) == 2000
