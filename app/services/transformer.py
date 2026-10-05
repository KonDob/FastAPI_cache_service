"""Simulated external transformer service.

The task treats the transformation as a call to a slow, external service, so it is
kept behind a narrow batch interface and injected as a dependency: the payload
service never knows it is just `str.upper`, and tests can swap in a counting fake.
"""

import logging
import time
from collections.abc import Sequence
from typing import Annotated, Protocol

from fastapi import Depends

from app.core.config import settings

logger = logging.getLogger(__name__)


class Transformer(Protocol):
    def __call__(self, values: Sequence[str]) -> list[str]:
        """Transform values in one round trip; the result is aligned with the input."""
        ...


def upper_case_transformer(values: Sequence[str]) -> list[str]:
    logger.info("Transformer service called with %d string(s)", len(values))
    # Latency is per call, as with a real remote batch API.
    time.sleep(settings.transformer_delay_seconds)
    return [value.upper() for value in values]


def get_transformer() -> Transformer:
    return upper_case_transformer


TransformerDep = Annotated[Transformer, Depends(get_transformer)]
