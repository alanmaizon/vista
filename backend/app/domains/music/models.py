"""Database models owned by the Eurydice music domain."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ...models import Base


class MusicScore(Base):
    """Persisted symbolic score data for Eurydice."""

    __tablename__ = "music_scores"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: str = Column(String, nullable=False)
    session_id: Optional[uuid.UUID] = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source_format: str = Column(String(32), nullable=False)
    time_signature: str = Column(String(16), nullable=False, default="4/4", server_default="4/4")
    note_count: int = Column(Integer, nullable=False)
    normalized: str = Column(Text, nullable=False)
    summary: str = Column(Text, nullable=False)
    warnings: list[str] | None = Column(JSONB, nullable=True)
    measures: list[dict] = Column(JSONB, nullable=False)
