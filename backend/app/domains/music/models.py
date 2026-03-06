"""Database models owned by the Eurydice music domain."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
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


class MusicSkillProfile(Base):
    """Deterministic adaptive profile snapshot for one Eurydice user."""

    __tablename__ = "music_skill_profiles"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: str = Column(String, nullable=False, unique=True, index=True)
    instrument_profile: str = Column(String(16), nullable=False, default="AUTO", server_default="AUTO")

    sample_count: int = Column(Integer, nullable=False, default=0, server_default="0")
    weakest_dimension: str = Column(String(24), nullable=False, default="pitch", server_default="pitch")

    consistency_score: float = Column(Float, nullable=False, default=0.5, server_default="0.5")
    consistency_jitter: float = Column(Float, nullable=False, default=0.0, server_default="0")
    practice_frequency: float = Column(Float, nullable=False, default=0.0, server_default="0")
    last_improvement_trend: float = Column(Float, nullable=False, default=0.0, server_default="0")
    overall_score: float = Column(Float, nullable=False, default=0.0, server_default="0")

    pitch_score: float = Column(Float, nullable=False, default=0.0, server_default="0")
    rhythm_score: float = Column(Float, nullable=False, default=0.0, server_default="0")
    tempo_score: float = Column(Float, nullable=False, default=0.0, server_default="0")
    dynamics_score: float = Column(Float, nullable=False, default=0.0, server_default="0")
    articulation_score: float = Column(Float, nullable=False, default=0.0, server_default="0")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_practiced_at = Column(DateTime(timezone=True), nullable=True)


class MusicPerformanceAttempt(Base):
    """Captured compare-attempt summary used by analytics timelines and heatmaps."""

    __tablename__ = "music_performance_attempts"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: str = Column(String, nullable=False, index=True)
    score_id: Optional[uuid.UUID] = Column(UUID(as_uuid=True), nullable=True, index=True)
    measure_index: Optional[int] = Column(Integer, nullable=True, index=True)
    instrument_profile: str = Column(String(16), nullable=False, default="AUTO", server_default="AUTO")

    accuracy: float = Column(Float, nullable=False)
    match: bool = Column(Boolean, nullable=False, default=False, server_default="false")
    needs_replay: bool = Column(Boolean, nullable=False, default=False, server_default="false")
    summary: str = Column(Text, nullable=False)
    performance_feedback: dict | None = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MusicLessonAssignment(Base):
    """Teacher-assigned lesson work item for one student."""

    __tablename__ = "music_lesson_assignments"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_user_id: str = Column(String, nullable=False, index=True)
    student_user_id: str = Column(String, nullable=False, index=True)
    score_id: Optional[uuid.UUID] = Column(UUID(as_uuid=True), nullable=True, index=True)

    title: str = Column(String(160), nullable=False)
    instructions: str = Column(Text, nullable=False, default="", server_default="")
    status: str = Column(String(24), nullable=False, default="ASSIGNED", server_default="ASSIGNED")
    target_measures: list[int] | None = Column(JSONB, nullable=True)

    due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
