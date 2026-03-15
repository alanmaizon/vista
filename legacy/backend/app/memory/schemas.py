"""Structured data types for the musical memory system."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Categories of memories the system can store."""

    THEORY_EXPLANATION = "theory_explanation"
    PRACTICE_ATTEMPT = "practice_attempt"
    CORRECTION_FEEDBACK = "correction_feedback"
    LESSON_SUMMARY = "lesson_summary"
    USER_QUESTION = "user_question"
    ANALYSIS_RESULT = "analysis_result"


class MusicalMemoryMetadata(BaseModel):
    """Optional metadata attached to a musical memory."""

    scale: Optional[str] = None
    tempo: Optional[float] = None
    accuracy: Optional[float] = None
    notes_played: Optional[list[str]] = None
    instrument: Optional[str] = None
    difficulty: Optional[str] = None
    session_skill: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class MusicalMemory(BaseModel):
    """A single unit of musical memory stored with its embedding."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    memory_type: MemoryType
    content: str
    embedding: Optional[list[float]] = None
    metadata: MusicalMemoryMetadata = Field(default_factory=MusicalMemoryMetadata)


class MemorySearchResult(BaseModel):
    """A memory returned from a similarity search with its score."""

    memory: MusicalMemory
    score: float = Field(ge=0.0, le=1.0, description="Cosine similarity score (higher is more relevant)")


class SessionSummary(BaseModel):
    """Structured summary generated at the end of a practice session."""

    session_id: str
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scales_practiced: list[str] = Field(default_factory=list)
    mistakes_detected: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    overall_accuracy: Optional[float] = None
    session_skill: Optional[str] = None
    raw_summary: str = ""
