"""Music API routes for Eurydice."""

from __future__ import annotations

from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator

from ... import auth as auth_utils
from ...db import get_db
from .crepe import crepe_runtime_status
from .symbolic import import_simple_score, score_to_dict
from .transcription import (
    decode_audio_b64,
    parse_pcm_mime,
    transcribe_pcm16,
    transcription_to_dict,
)
from .compare import compare_performance_against_score, comparison_to_dict
from .models import MusicScore
from .render import render_music_score, verovio_runtime_status


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


class MusicScoreRenderResponse(BaseModel):
    """Rendered notation payload for a stored score."""

    score_id: UUID
    render_backend: str
    verovio_available: bool
    musicxml: str
    svg: str | None
    warnings: list[str]
    expected_notes: list[dict]
    note_layout: list[dict]


class MusicScorePrepareResponse(MusicScoreImportResponse):
    """Prepared score payload including render output."""

    render_backend: str
    verovio_available: bool
    musicxml: str
    svg: str | None
    expected_notes: list[dict]
    note_layout: list[dict]


class MusicPerformanceCompareRequest(BaseModel):
    """Request body for comparing a played phrase against a stored score."""

    audio_b64: str = Field(..., description="Base64-encoded mono PCM16 audio clip.")
    mime: str = Field("audio/pcm;rate=16000", description="PCM mime type, e.g. audio/pcm;rate=16000")
    max_notes: int = Field(12, ge=1, le=12, description="Maximum note events to evaluate from the performance.")
    measure_index: int | None = Field(
        None,
        ge=1,
        description="Optional 1-based measure index to compare instead of the entire stored score.",
    )

    @field_validator("audio_b64")
    @classmethod
    def validate_audio_b64(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("audio_b64 is required.")
        return value


class MusicPerformanceCompareResponse(BaseModel):
    """Comparison result between a target phrase and the performed phrase."""

    score_id: UUID
    needs_replay: bool
    match: bool
    accuracy: float
    summary: str
    warnings: list[str]
    mismatches: list[str]
    expected_notes: list[dict]
    played_phrase: dict
    comparisons: list[dict]


class MusicLessonStepRequest(BaseModel):
    """Request body for guided lesson progression."""

    current_measure_index: int | None = Field(
        None,
        ge=1,
        description="Current 1-based measure index in the lesson, or null to start from bar 1.",
    )
    lesson_stage: Literal["idle", "awaiting-compare", "reviewed", "complete"] = Field(
        "idle",
        description="Current frontend lesson stage.",
    )


class MusicLessonStepResponse(BaseModel):
    """Next-step guidance for a guided lesson."""

    score_id: UUID
    lesson_stage: Literal["awaiting-compare", "complete"]
    lesson_complete: bool
    measure_index: int | None
    total_measures: int
    prompt: str
    status: str
    note_start_index: int | None
    note_end_index: int | None


class MusicLessonActionRequest(BaseModel):
    """Request body for the main guided-lesson action."""

    score_id: UUID | None = Field(
        None,
        description="Existing prepared score. Omit to prepare a new score from source_text.",
    )
    source_text: str | None = Field(
        None,
        description="Simple note-line source used when no score_id is provided.",
    )
    time_signature: str = Field("4/4", description="Expected time signature for score preparation.")
    current_measure_index: int | None = Field(
        None,
        ge=1,
        description="Current 1-based measure index in the lesson, if a score is already active.",
    )
    lesson_stage: Literal["idle", "awaiting-compare", "reviewed", "complete"] = Field(
        "idle",
        description="Current guided-lesson stage.",
    )
    audio_b64: str | None = Field(
        None,
        description="Optional base64-encoded mono PCM16 audio clip for the compare step.",
    )
    mime: str = Field("audio/pcm;rate=16000", description="PCM mime type for audio_b64.")
    max_notes: int = Field(12, ge=1, le=12, description="Maximum note events to evaluate when comparing.")


class MusicLessonActionResponse(BaseModel):
    """Unified guided-lesson response for prepare, advance, and compare."""

    outcome: Literal["awaiting-compare", "reviewed", "complete"]
    score: MusicScorePrepareResponse | None = None
    lesson: MusicLessonStepResponse | None = None
    comparison: MusicPerformanceCompareResponse | None = None


class MusicRuntimeStatusResponse(BaseModel):
    """Runtime diagnostics for Eurydice integrations."""

    verovio_available: bool
    verovio_detail: str
    crepe_available: bool
    crepe_detail: str


async def _get_owned_score(db: AsyncSession, score_id: UUID, user_id: str) -> MusicScore:
    result = await db.execute(select(MusicScore).where(MusicScore.id == score_id))
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found")
    if score.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorised to access this score")
    return score


def _flatten_expected_notes(score: MusicScore) -> list[dict]:
    return [note for measure in (score.measures or []) for note in measure.get("notes", [])]


def _measure_note_range(score: MusicScore, measure_index: int) -> tuple[int, int]:
    measures = list(score.measures or [])
    start = 0
    for measure in measures[: measure_index - 1]:
        start += len(measure.get("notes", []))
    count = len(measures[measure_index - 1].get("notes", []))
    return start, start + count


def _guided_lesson_prompt(score: MusicScore, measure_index: int) -> str:
    measures = list(score.measures or [])
    measure = measures[measure_index - 1]
    note_names = [note.get("note_name", "?") for note in measure.get("notes", [])]
    if note_names:
        readable_notes = ", ".join(note_names)
        return f"Bar {measure_index}: play {readable_notes}. Then compare your take."
    return f"Play bar {measure_index} clearly, then compare your take."


def _prepare_music_score_payload(score, stored_score: MusicScore, time_signature: str) -> MusicScorePrepareResponse:
    rendered = render_music_score(stored_score)
    return MusicScorePrepareResponse(
        score_id=stored_score.id,
        format=score.format,
        time_signature=time_signature,
        note_count=score.note_count,
        normalized=score.normalized,
        summary=score.summary,
        warnings=list(score.warnings),
        measures=score_to_dict(score)["measures"],
        render_backend=rendered.render_backend,
        verovio_available=rendered.verovio_available,
        musicxml=rendered.musicxml,
        svg=rendered.svg,
        expected_notes=_flatten_expected_notes(stored_score),
        note_layout=list(rendered.note_layout),
    )


def _build_lesson_step_from_score(score: MusicScore, payload: MusicLessonStepRequest) -> MusicLessonStepResponse:
    measures = list(score.measures or [])
    total_measures = len(measures)
    if total_measures == 0:
        raise HTTPException(status_code=400, detail="The prepared score does not contain readable bars yet.")

    current_measure = payload.current_measure_index
    if current_measure is not None and current_measure > total_measures:
        raise HTTPException(status_code=400, detail="current_measure_index is outside the stored score.")

    if payload.lesson_stage == "reviewed" and current_measure is not None and current_measure >= total_measures:
        return MusicLessonStepResponse(
            score_id=score.id,
            lesson_stage="complete",
            lesson_complete=True,
            measure_index=None,
            total_measures=total_measures,
            prompt="Lesson complete. Use the main button to restart from bar 1 if you want another pass.",
            status="Lesson complete.",
            note_start_index=None,
            note_end_index=None,
        )

    if payload.lesson_stage == "complete":
        next_measure = 1
    elif current_measure is None:
        next_measure = 1
    elif payload.lesson_stage == "reviewed":
        next_measure = current_measure + 1
    else:
        next_measure = current_measure

    start_index, end_index = _measure_note_range(score, next_measure)
    return MusicLessonStepResponse(
        score_id=score.id,
        lesson_stage="awaiting-compare",
        lesson_complete=False,
        measure_index=next_measure,
        total_measures=total_measures,
        prompt=_guided_lesson_prompt(score, next_measure),
        status=f"Lesson ready for bar {next_measure}.",
        note_start_index=start_index,
        note_end_index=end_index,
    )


def _build_compare_score(score: MusicScore, measure_index: int | None) -> MusicScore:
    if measure_index is None:
        return score
    measures = list(score.measures or [])
    if measure_index > len(measures):
        raise HTTPException(status_code=400, detail="measure_index is outside the stored score.")
    selected_measure = measures[measure_index - 1]
    return MusicScore(
        id=score.id,
        user_id=score.user_id,
        source_format=score.source_format,
        time_signature=score.time_signature,
        note_count=len(selected_measure.get("notes", [])),
        normalized=score.normalized,
        summary=score.summary,
        warnings=list(score.warnings or []),
        measures=[selected_measure],
    )


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


@router.get("/runtime", response_model=MusicRuntimeStatusResponse)
async def music_runtime_status(
    current_user: dict = Depends(auth_utils.get_current_user),
) -> MusicRuntimeStatusResponse:
    """Expose music runtime diagnostics for the Eurydice client."""
    del current_user

    available, detail = verovio_runtime_status()
    crepe_available, crepe_detail = crepe_runtime_status()
    return MusicRuntimeStatusResponse(
        verovio_available=available,
        verovio_detail=detail,
        crepe_available=crepe_available,
        crepe_detail=crepe_detail,
    )


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


@router.post("/score/prepare", response_model=MusicScorePrepareResponse)
async def prepare_music_score(
    payload: MusicScoreImportRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicScorePrepareResponse:
    """Import and render a score in one backend step for guided workflows."""
    score = import_simple_score(payload.source_text, time_signature=payload.time_signature)
    measures = score_to_dict(score)["measures"]

    stored_score = MusicScore(
        user_id=current_user["uid"],
        source_format=score.format,
        time_signature=payload.time_signature,
        note_count=score.note_count,
        normalized=score.normalized,
        summary=score.summary,
        warnings=list(score.warnings),
        measures=measures,
    )
    if payload.persist:
        db.add(stored_score)
        await db.commit()
        await db.refresh(stored_score)
    prepared = _prepare_music_score_payload(score, stored_score, payload.time_signature)
    if not payload.persist:
        prepared.score_id = None
    return prepared


@router.get("/score/{score_id}", response_model=MusicScoreImportResponse)
async def get_music_score(
    score_id: UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicScoreImportResponse:
    """Fetch a stored symbolic score owned by the current user."""
    score = await _get_owned_score(db, score_id, current_user["uid"])

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


@router.get("/score/{score_id}/render", response_model=MusicScoreRenderResponse)
async def render_stored_music_score(
    score_id: UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicScoreRenderResponse:
    """Render a stored score into MusicXML and, when available, Verovio SVG."""
    score = await _get_owned_score(db, score_id, current_user["uid"])
    rendered = render_music_score(score)
    return MusicScoreRenderResponse(
        score_id=score.id,
        render_backend=rendered.render_backend,
        verovio_available=rendered.verovio_available,
        musicxml=rendered.musicxml,
        svg=rendered.svg,
        warnings=list(rendered.warnings),
        expected_notes=_flatten_expected_notes(score),
        note_layout=list(rendered.note_layout),
    )


@router.post("/score/{score_id}/lesson-step", response_model=MusicLessonStepResponse)
async def next_guided_lesson_step(
    score_id: UUID,
    payload: MusicLessonStepRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLessonStepResponse:
    """Return the next guided-lesson step for a stored score."""
    score = await _get_owned_score(db, score_id, current_user["uid"])
    return _build_lesson_step_from_score(score, payload)


@router.post("/score/{score_id}/compare", response_model=MusicPerformanceCompareResponse)
async def compare_performance_with_score(
    score_id: UUID,
    payload: MusicPerformanceCompareRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicPerformanceCompareResponse:
    """Compare a short played phrase against a stored symbolic score."""
    score = await _get_owned_score(db, score_id, current_user["uid"])
    compare_score = _build_compare_score(score, payload.measure_index)
    sample_rate = parse_pcm_mime(payload.mime)
    audio_bytes = decode_audio_b64(payload.audio_b64)
    result = compare_performance_against_score(
        compare_score,
        audio_bytes=audio_bytes,
        sample_rate=sample_rate,
        max_notes=payload.max_notes,
    )
    return MusicPerformanceCompareResponse(
        score_id=score.id,
        **comparison_to_dict(result),
    )


@router.post("/lesson-action", response_model=MusicLessonActionResponse)
async def run_guided_lesson_action(
    payload: MusicLessonActionRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLessonActionResponse:
    """Perform the main guided-lesson action: prepare, advance, or compare."""
    score: MusicScore
    prepared_payload: MusicScorePrepareResponse | None = None

    if payload.score_id is None:
        source_text = (payload.source_text or "").strip()
        if not source_text:
            raise HTTPException(status_code=400, detail="source_text is required when score_id is not provided.")
        imported = import_simple_score(source_text, time_signature=payload.time_signature)
        stored_score = MusicScore(
            user_id=current_user["uid"],
            source_format=imported.format,
            time_signature=payload.time_signature,
            note_count=imported.note_count,
            normalized=imported.normalized,
            summary=imported.summary,
            warnings=list(imported.warnings),
            measures=score_to_dict(imported)["measures"],
        )
        db.add(stored_score)
        await db.commit()
        await db.refresh(stored_score)
        score = stored_score
        prepared_payload = _prepare_music_score_payload(imported, stored_score, payload.time_signature)
    else:
        score = await _get_owned_score(db, payload.score_id, current_user["uid"])

    if payload.lesson_stage == "awaiting-compare":
        if not payload.audio_b64:
            raise HTTPException(status_code=400, detail="audio_b64 is required while the lesson is awaiting comparison.")
        compare_score = _build_compare_score(score, payload.current_measure_index or 1)
        sample_rate = parse_pcm_mime(payload.mime)
        audio_bytes = decode_audio_b64(payload.audio_b64)
        result = compare_performance_against_score(
            compare_score,
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            max_notes=payload.max_notes,
        )
        comparison = MusicPerformanceCompareResponse(
            score_id=score.id,
            **comparison_to_dict(result),
        )
        return MusicLessonActionResponse(
            outcome="awaiting-compare" if result.needs_replay or not result.match else "reviewed",
            score=prepared_payload,
            comparison=comparison,
        )

    lesson = _build_lesson_step_from_score(
        score,
        MusicLessonStepRequest(
            current_measure_index=payload.current_measure_index,
            lesson_stage=payload.lesson_stage,
        ),
    )
    return MusicLessonActionResponse(
        outcome="complete" if lesson.lesson_complete else "awaiting-compare",
        score=prepared_payload,
        lesson=lesson,
    )
