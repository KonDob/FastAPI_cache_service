"""Payload creation and lookup.

The transformer and its per-string cache land in a follow-up change; for now the
output is produced by a placeholder so persistence can be reviewed on its own.
"""

import hashlib
import json
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Payload


class CreateResult(NamedTuple):
    id: UUID
    # Lets the API tell a freshly generated payload from a reused one.
    created: bool


def create_payload(session: Session, list_1: list[str], list_2: list[str]) -> CreateResult:
    input_hash = _hash_input(list_1, list_2)
    existing_id = _find_id_by_hash(session, input_hash)
    if existing_id is not None:
        return CreateResult(id=existing_id, created=False)

    payload = Payload(input_hash=input_hash, output=_build_output(list_1, list_2))
    session.add(payload)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request stored the same input between our lookup and insert.
        session.rollback()
        winner_id = _find_id_by_hash(session, input_hash)
        if winner_id is None:
            raise
        return CreateResult(id=winner_id, created=False)
    return CreateResult(id=payload.id, created=True)


def get_payload(session: Session, payload_id: UUID) -> str | None:
    payload = session.get(Payload, payload_id)
    return payload.output if payload is not None else None


def _hash_input(list_1: list[str], list_2: list[str]) -> str:
    # JSON keeps list boundaries unambiguous: ["a,b"] and ["a", "b"] hash differently.
    canonical = json.dumps([list_1, list_2], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _find_id_by_hash(session: Session, input_hash: str) -> UUID | None:
    return session.scalar(select(Payload.id).where(Payload.input_hash == input_hash))


def _build_output(list_1: list[str], list_2: list[str]) -> str:
    # Placeholder output: enough for the API contract, not the final algorithm.
    interleaved = [item for pair in zip(list_1, list_2, strict=True) for item in pair]
    return ", ".join(value.upper() for value in interleaved)
