"""Music API routes for Eurydice."""

from __future__ import annotations

from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator

from . import auth as auth_utils
from .db import get_db
from .models import MusicScore
from .music_symbolic import import_simple_score, score_to_dict
from .music_transcription import (
    decode_audio_b64,
    parse_pcm_mime,
    transcribe_pcm16,
    transcription_to_dict,
)


router = APIRouter(prefix="/api/music", tags=["music"])


class MusicTranscriptionRequest(BaseModel):
    """Request body for one-shot phrase transcription."""

    audio_b64: str = Field(..., description="Base64-encoded mono PCM16 audio clip.")
    mime: str = Field("audio/pcm;rate=16000", description="PCM mime type, e.g. audio/pcm;rate=16000")
    expected: Literal["AUTO", "NOTE", "INTERVAL", "ARPEGGIO", "CHORD", "PHRASE"] = Field(
        "AUTO",
        description="What the user expects to have played. Used to shape warnings only.",
    )
    max_notes: int = Field(8, ge=1, le=12, description="Maximum note events to return.")

    @field_validator("audio_b64")
    @classmethod
    def validate_audio_b64(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("audio_b64 is required.")
        return value


class MusicTranscriptionResponse(BaseModel):
    """Transcription result for a short phrase."""

    kind: str
    duration_ms: int
    confidence: float
    interval_hint: str | None
    harmony_hint: str | None
    summary: str
    warnings: list[str]
    notes: list[dict]


class MusicScoreImportRequest(BaseModel):
    """Request body for a first symbolic score import."""

    source_text: str = Field(..., description="Simple note-line source, e.g. 'C4/q D4/q | E4/h G4/h'")
    source_format: Literal["NOTE_LINE"] = Field(
        "NOTE_LINE",
        description="Import format. The MVP currently supports only NOTE_LINE.",
    )
    time_signature: str = Field("4/4", description="Expected time signature for beat warnings.")
    persist: bool = Field(True, description="Whether the imported score should be stored for later use.")

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_text is required.")
        return value


class MusicScoreImportResponse(BaseModel):
    """Imported symbolic score payload."""

    score_id: UUID | None = None
    format: str
    time_signature: str
    note_count: int
    normalized: str
    summary: str
    warnings: list[str]
    measures: list[dict]


@router.post("/transcribe", response_model=MusicTranscriptionResponse)
async def transcribe_music(
    payload: MusicTranscriptionRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
) -> MusicTranscriptionResponse:
    """Transcribe a short monophonic phrase into a symbolic note sequence."""
    del current_user

    sample_rate = parse_pcm_mime(payload.mime)
    audio_bytes = decode_audio_b64(payload.audio_b64)
    result = transcribe_pcm16(
        audio_bytes,
        sample_rate=sample_rate,
        expected=payload.expected,
        max_notes=payload.max_notes,
    )
    return MusicTranscriptionResponse(**transcription_to_dict(result))


@router.post("/score/import", response_model=MusicScoreImportResponse)
async def import_music_score(
    payload: MusicScoreImportRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicScoreImportResponse:
    """Import a minimal symbolic score from a simple note-line format."""
    score = import_simple_score(payload.source_text, time_signature=payload.time_signature)
    result = {
        "score_id": None,
        "time_signature": payload.time_signature,
        **score_to_dict(score),
    }

    if payload.persist:
        stored_score = MusicScore(
            user_id=current_user["uid"],
            source_format=score.format,
            time_signature=payload.time_signature,
            note_count=score.note_count,
            normalized=score.normalized,
            summary=score.summary,
            warnings=list(score.warnings),
            measures=result["measures"],
        )
        db.add(stored_score)
        await db.commit()
        await db.refresh(stored_score)
        result["score_id"] = stored_score.id

    return MusicScoreImportResponse(**result)


@router.get("/score/{score_id}", response_model=MusicScoreImportResponse)
async def get_music_score(
    score_id: UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicScoreImportResponse:
    """Fetch a stored symbolic score owned by the current user."""
    result = await db.execute(select(MusicScore).where(MusicScore.id == score_id))
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found")
    if score.user_id != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorised to access this score")

    return MusicScoreImportResponse(
        score_id=score.id,
        format=score.source_format,
        time_signature=score.time_signature,
        note_count=score.note_count,
        normalized=score.normalized,
        summary=score.summary,
        warnings=list(score.warnings or []),
        measures=list(score.measures or []),
    )
