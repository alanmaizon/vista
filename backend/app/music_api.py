"""Music API routes for Eurydice."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from . import auth as auth_utils
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
