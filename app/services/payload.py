"""Payload service stubs.

Real transformer caching and PostgreSQL persistence land in a follow-up change.
These stubs keep the HTTP layer testable and reviewable on its own.
"""

from uuid import UUID, uuid4

# In-memory stand-in until the database layer exists.
_STORE: dict[UUID, str] = {}


def create_payload(list_1: list[str], list_2: list[str]) -> UUID:
    payload_id = uuid4()
    # Placeholder output: enough for the API contract, not the final algorithm.
    interleaved = [item for pair in zip(list_1, list_2, strict=True) for item in pair]
    _STORE[payload_id] = ", ".join(value.upper() for value in interleaved)
    return payload_id


def get_payload(payload_id: UUID) -> str | None:
    return _STORE.get(payload_id)
