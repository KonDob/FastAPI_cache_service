"""Application entrypoint."""

from fastapi import FastAPI

from app.api.routes import router as payload_router

app = FastAPI(
    title="FastAPI Caching Service",
    description="Generate interleaved payloads with a cached transformer.",
    version="0.1.0",
)
app.include_router(payload_router)
