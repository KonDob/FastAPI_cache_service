"""Races between requests, reproduced deterministically.

A competing request is run from inside the transformer call, i.e. exactly in the window
between this request's lookups and its inserts, so the conflict paths are always taken.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Payload, TransformCache
from app.services import payload as payload_service
from app.services.payload import CreateResult
from app.services.transformer import upper_case_transformer


def test_identical_payload_stored_concurrently_resolves_to_the_winner_id(
    session_factory: sessionmaker[Session],
) -> None:
    winner_ids: list[UUID] = []

    def transformer_losing_the_race(values: Sequence[str]) -> list[str]:
        with session_factory() as competitor:
            result = payload_service.create_payload(
                competitor, upper_case_transformer, ["a"], ["b"]
            )
            winner_ids.append(result.id)
        return upper_case_transformer(values)

    with session_factory() as session:
        result = payload_service.create_payload(session, transformer_losing_the_race, ["a"], ["b"])

    assert result == CreateResult(id=winner_ids[0], created=False)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Payload)) == 1


def test_string_cached_concurrently_by_another_payload_is_stored_once(
    session_factory: sessionmaker[Session],
) -> None:
    def transformer_losing_the_race(values: Sequence[str]) -> list[str]:
        with session_factory() as competitor:
            payload_service.create_payload(competitor, upper_case_transformer, ["shared"], ["x"])
        return upper_case_transformer(values)

    with session_factory() as session:
        result = payload_service.create_payload(
            session, transformer_losing_the_race, ["shared"], ["y"]
        )
        assert result.created
        assert payload_service.get_payload(session, result.id) == "SHARED, Y"

    with session_factory() as session:
        cached = session.scalars(select(TransformCache.input).order_by(TransformCache.input))
        assert list(cached) == ["shared", "x", "y"]
