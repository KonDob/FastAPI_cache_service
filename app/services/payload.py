"""Payload service stubs.

Real transformer caching and PostgreSQL persistence land in a follow-up change.
These stubs keep the HTTP layer testable and reviewable on its own.
"""

from typing import NamedTuple
from uuid import UUID, uuid4


class CreateResult(NamedTuple):
    id: UUID
    # Lets the API tell a freshly generated payload from a reused one.
    created: bool


# In-memory stand-ins until the database layer exists.
_STORE: dict[UUID, str] = {}
# Identical inputs must resolve to the same identifier, so we index by the input itself.
_IDS_BY_INPUT: dict[tuple[tuple[str, ...], tuple[str, ...]], UUID] = {}


def create_payload(list_1: list[str], list_2: list[str]) -> CreateResult:
    key = (tuple(list_1), tuple(list_2))
    existing_id = _IDS_BY_INPUT.get(key)
    if existing_id is not None:
        return CreateResult(id=existing_id, created=False)

    payload_id = uuid4()
    # Placeholder output: enough for the API contract, not the final algorithm.
    interleaved = [item for pair in zip(list_1, list_2, strict=True) for item in pair]
    _STORE[payload_id] = ", ".join(value.upper() for value in interleaved)
    _IDS_BY_INPUT[key] = payload_id
    return CreateResult(id=payload_id, created=True)


def get_payload(payload_id: UUID) -> str | None:
    return _STORE.get(payload_id)
