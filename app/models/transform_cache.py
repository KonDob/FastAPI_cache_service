"""Per-string cache of transformer results."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransformCache(Base):
    __tablename__ = "transform_cache"

    # Keyed by a hash rather than the string itself: a B-tree index on arbitrary-length
    # text breaks on long values, a fixed 64-char digest never does.
    input_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)
