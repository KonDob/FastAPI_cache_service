"""Error responses shared by all routes."""

import json
from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class _AsciiJSONResponse(JSONResponse):
    # Escapes non-ASCII instead of writing raw UTF-8: a validation error echoes the rejected
    # input, and input such as a lone surrogate cannot be encoded as UTF-8 at all.
    def render(self, content: Any) -> bytes:
        return json.dumps(content, allow_nan=False, separators=(",", ":")).encode("ascii")


async def request_validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Same body as FastAPI's default handler; only the encoding differs.
    assert isinstance(exc, RequestValidationError)
    return _AsciiJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(exc.errors())},
    )
