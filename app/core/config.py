"""Application settings loaded from the environment."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default matches docker-compose.yml so `uv run uvicorn ...` works out of the box.
    database_url: str = "postgresql+psycopg://cache:cache@localhost:5432/cache"
    # Simulated latency of the external transformer service, per batch call.
    transformer_delay_seconds: float = Field(default=0.5, ge=0)
    log_level: str = "INFO"


settings = Settings()
