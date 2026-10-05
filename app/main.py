"""Application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  # registers tables on Base.metadata
from app.api.routes import router as payload_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Shortcut instead of migrations: the schema is small and only ever grows here.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="FastAPI Caching Service",
    description="Generate interleaved payloads with a cached transformer.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(payload_router)
