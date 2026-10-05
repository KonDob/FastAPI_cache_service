"""Test doubles for the transformer service."""

from collections.abc import Sequence

from app.services.transformer import upper_case_transformer


class CountingTransformer:
    """Real transformation plus a record of every call, to assert on cache behaviour."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, values: Sequence[str]) -> list[str]:
        self.calls.append(list(values))
        return upper_case_transformer(values)
