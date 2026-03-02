"""Music API routes for Eurydice."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from . import auth as auth_utils
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

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_text is required.")
        return value


class MusicScoreImportResponse(BaseModel):
    """Imported symbolic score payload."""

    format: str
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
) -> MusicScoreImportResponse:
    """Import a minimal symbolic score from a simple note-line format."""
    del current_user

    score = import_simple_score(payload.source_text, time_signature=payload.time_signature)
    return MusicScoreImportResponse(**score_to_dict(score))
