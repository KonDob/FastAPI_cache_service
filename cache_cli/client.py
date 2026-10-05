"""Calls to the caching service."""

import time
from typing import Any, Literal

import httpx2
from pydantic import BaseModel

from cache_cli.settings import PayloadRequest


class ServiceError(Exception):
    """The service could not be reached or answered with an error."""


class IterationResult(BaseModel):
    iteration: int
    id: str
    # "existing" on repeats shows that the service reused the identifier.
    status: Literal["created", "existing"]
    output: str
    elapsed_ms: float


def run(client: httpx2.Client, request: PayloadRequest, repeat: int) -> list[IterationResult]:
    """Create the payload and read it back, `repeat` times; stop at the first failure."""
    return [_run_once(client, request, iteration) for iteration in range(1, repeat + 1)]


def _run_once(client: httpx2.Client, request: PayloadRequest, iteration: int) -> IterationResult:
    started = time.perf_counter()
    created = _call(client, "POST", "/payload", json=request.model_dump())
    payload_id = created.json()["id"]
    read = _call(client, "GET", f"/payload/{payload_id}")
    return IterationResult(
        iteration=iteration,
        id=payload_id,
        status="created" if created.status_code == httpx2.codes.CREATED else "existing",
        output=read.json()["output"],
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )


def _call(client: httpx2.Client, method: str, url: str, json: Any = None) -> httpx2.Response:
    try:
        response = client.request(method, url, json=json)
    except httpx2.HTTPError as error:
        raise ServiceError(f"{method} {url} failed: {error}") from error
    if response.is_error:
        raise ServiceError(f"{method} {url} returned {response.status_code}: {response.text}")
    return response
