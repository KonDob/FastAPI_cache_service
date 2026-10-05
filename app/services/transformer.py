"""Simulated external transformer service.

The task treats the transformation as a call to an external service, so it is
kept behind a narrow batch interface and injected as a dependency: the payload
service never knows it is just `str.upper`, and tests can swap in a counting fake.
"""

import logging
from collections.abc import Sequence
from typing import Annotated, Protocol

from fastapi import Depends

logger = logging.getLogger(__name__)


class TransformerError(Exception):
    """The transformer service failed or broke its contract."""


class Transformer(Protocol):
    def __call__(self, values: Sequence[str]) -> list[str]:
        """Transform values in one round trip; the result is aligned with the input.

        Implementations raise TransformerError when the service cannot be used, so callers
        handle one error type regardless of the transport behind it.
        """
        ...


def upper_case_transformer(values: Sequence[str]) -> list[str]:
    logger.info("Transformer service called with %d string(s)", len(values))
    return [value.upper() for value in values]


def get_transformer() -> Transformer:
    return upper_case_transformer


TransformerDep = Annotated[Transformer, Depends(get_transformer)]
