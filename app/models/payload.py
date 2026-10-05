"""Generated payloads."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payload(Base):
    __tablename__ = "payload"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Fingerprint of the input lists; the unique constraint is what guarantees that
    # identical requests share one id, even when they race each other.
    input_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Stored ready-made: a payload never changes, so GET should not rebuild it.
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
