"""SQLAlchemy models for the Vista AI application.

The application tracks user sessions for each interaction with the
assistant.  Each session stores metadata such as the user ID, the
selected mode (skill), risk mode, start/end timestamps, and a JSON
summary of the completed task.  Additional models can be added in
future to support user preferences and other features.
"""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase

from .domains.base import DEFAULT_DOMAIN


class Base(DeclarativeBase):
    pass


class Session(Base):
    """Represents a single user interaction session.

    The `id` is a UUID to uniquely identify the session.  The `user_id`
    stores the Firebase UID of the authenticated user (as a string).
    The `mode` field records which skill was selected (e.g.
    NAV_FIND, SHOP_VERIFY, etc.).  The `risk_mode` tracks whether the
    session entered a caution or refusal state.  The `goal` holds a
    short description of the user's requested task.  The optional
    `summary` stores a JSON structure capturing final bullets and other
    structured outputs.  The `success` flag indicates whether the
    session completed successfully.
    """

    __tablename__ = "sessions"

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: str = Column(String, nullable=False)

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    domain: str = Column(String(16), nullable=False, default=DEFAULT_DOMAIN, server_default=DEFAULT_DOMAIN)
    mode: str = Column(String(32), nullable=False)
    risk_mode: str = Column(String(16), nullable=False, default="NORMAL")
    goal: Optional[str] = Column(String(256), nullable=True)

    summary: Optional[dict] = Column(JSONB, nullable=True)
    success: Optional[bool] = Column(Boolean, nullable=True)

    model_id: Optional[str] = Column(String(128), nullable=True)
    region: Optional[str] = Column(String(32), nullable=True)


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
