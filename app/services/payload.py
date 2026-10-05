"""Payload creation and lookup."""

import hashlib
import json
import logging
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Payload, TransformCache
from app.services.transformer import Transformer

logger = logging.getLogger(__name__)


class CreateResult(NamedTuple):
    id: UUID
    # Lets the API tell a freshly generated payload from a reused one.
    created: bool


def create_payload(
    session: Session, transformer: Transformer, list_1: list[str], list_2: list[str]
) -> CreateResult:
    input_hash = _hash_input(list_1, list_2)
    existing_id = _find_id_by_hash(session, input_hash)
    if existing_id is not None:
        return CreateResult(id=existing_id, created=False)

    transformed = _transform_cached(session, transformer, [*list_1, *list_2])
    output = ", ".join(interleave([transformed[v] for v in list_1], [transformed[v] for v in list_2]))
    payload = Payload(input_hash=input_hash, output=output)
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
    return _sha256(canonical)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _find_id_by_hash(session: Session, input_hash: str) -> UUID | None:
    return session.scalar(select(Payload.id).where(Payload.input_hash == input_hash))


def interleave(first: list[str], second: list[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]


def _transform_cached(
    session: Session, transformer: Transformer, values: list[str]
) -> dict[str, str]:
    """Map each value to its transformation, calling the service only for unseen strings."""
    # A string repeated within one request is looked up and sent to the service only once.
    hashes = {value: _sha256(value) for value in dict.fromkeys(values)}
    cached = dict(
        session.execute(
            select(TransformCache.input_hash, TransformCache.output).where(
                TransformCache.input_hash.in_(hashes.values())
            )
        ).tuples().all()
    )
    result = {value: cached[h] for value, h in hashes.items() if h in cached}
    missing = [value for value in hashes if value not in result]
    logger.info("Transform cache: %d hit(s), %d miss(es)", len(result), len(missing))
    if not missing:
        return result

    fresh = dict(zip(missing, transformer(missing), strict=True))
    rows = [{"input_hash": hashes[v], "input": v, "output": out} for v, out in fresh.items()]
    # Concurrent requests may cache the same string; the first writer wins, others are no-ops.
    session.execute(insert(TransformCache).values(rows).on_conflict_do_nothing())
    # Committed on its own so a later failure cannot throw away results we already paid for.
    session.commit()
    return result | fresh
