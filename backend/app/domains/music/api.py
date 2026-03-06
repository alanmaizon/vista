"""Music API routes for Eurydice."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator

from ... import auth as auth_utils
from ...db import get_db
from .adaptive import update_user_skill_profile
from .crepe import crepe_runtime_status
from .symbolic import import_simple_score, score_to_dict
from .transcription import (
    decode_audio_b64,
    parse_pcm_mime,
    transcribe_pcm16,
    transcription_to_dict,
)
from .compare import compare_performance_against_score, comparison_to_dict
from .models import MusicLessonAssignment, MusicPerformanceAttempt, MusicScore, MusicSkillProfile
from .render import render_music_score, verovio_runtime_status


router = APIRouter(prefix="/api/music", tags=["music"])
InstrumentProfileLiteral = Literal["AUTO", "VOICE", "PIANO", "GUITAR", "STRINGS", "WINDS", "PERCUSSION"]
_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


class MusicTranscriptionRequest(BaseModel):
    """Request body for one-shot phrase transcription."""

    audio_b64: str = Field(..., description="Base64-encoded mono PCM16 audio clip.")
    mime: str = Field("audio/pcm;rate=16000", description="PCM mime type, e.g. audio/pcm;rate=16000")
    expected: Literal["AUTO", "NOTE", "INTERVAL", "ARPEGGIO", "CHORD", "PHRASE"] = Field(
        "AUTO",
        description="What the user expects to have played. Used to shape warnings only.",
    )
    max_notes: int = Field(8, ge=1, le=12, description="Maximum note events to return.")
    instrument_profile: InstrumentProfileLiteral = Field(
        "AUTO",
        description="Calibration profile for pitch/rhythm scoring strictness.",
    )

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
    performance_feedback: dict[str, float]
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
    instrument_profile: InstrumentProfileLiteral = Field(
        "AUTO",
        description="Calibration profile for expected-vs-played matching strictness.",
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
    performance_feedback: dict[str, float]


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
    instrument_profile: InstrumentProfileLiteral = Field(
        "AUTO",
        description="Calibration profile for lesson compare scoring.",
    )


class MusicLessonActionResponse(BaseModel):
    """Unified guided-lesson response for prepare, advance, and compare."""

    outcome: Literal["awaiting-compare", "reviewed", "complete"]
    score: MusicScorePrepareResponse | None = None
    lesson: MusicLessonStepResponse | None = None
    comparison: MusicPerformanceCompareResponse | None = None
    user_skill_profile: dict[str, object] | None = None
    next_drills: list[dict[str, object]] | None = None
    tutor_prompt: str | None = None


class MusicRuntimeStatusResponse(BaseModel):
    """Runtime diagnostics for Eurydice integrations."""

    verovio_available: bool
    verovio_detail: str
    crepe_available: bool
    crepe_detail: str


class MusicProgressSnapshotResponse(BaseModel):
    """Per-user adaptive progress payload for analytics surfaces."""

    user_id: str
    has_profile: bool
    sample_count: int
    weakest_dimension: str | None
    consistency_score: float
    practice_frequency: float
    last_improvement_trend: float
    overall_score: float
    rolling_metrics: dict[str, float]


class MusicTeacherStudentSummary(BaseModel):
    """Teacher-facing summary row for one student profile."""

    user_id: str
    sample_count: int
    weakest_dimension: str
    consistency_score: float
    practice_frequency: float
    overall_score: float
    last_improvement_trend: float


class MusicTeacherStudentsResponse(BaseModel):
    """Teacher dashboard roster payload."""

    students: list[MusicTeacherStudentSummary]


class MusicTeacherAssignmentCreateRequest(BaseModel):
    """Create one teacher assignment for a student."""

    student_user_id: str = Field(..., description="Student uid.")
    score_id: UUID | None = Field(None, description="Optional prepared score id.")
    title: str = Field(..., min_length=3, max_length=160)
    instructions: str = Field("", max_length=3000)
    target_measures: list[int] = Field(default_factory=list)
    due_at: datetime | None = Field(None, description="Optional due timestamp (ISO8601).")


class MusicTeacherAssignmentResponse(BaseModel):
    """Teacher assignment payload."""

    assignment_id: UUID
    teacher_user_id: str
    student_user_id: str
    score_id: UUID | None
    title: str
    instructions: str
    status: str
    target_measures: list[int]
    due_at: str | None
    created_at: str | None


class MusicTeacherAssignmentsResponse(BaseModel):
    """Teacher assignment roster payload."""

    assignments: list[MusicTeacherAssignmentResponse]


class MusicPerformanceAttemptSummary(BaseModel):
    """Performance timeline row."""

    attempt_id: UUID
    created_at: str | None
    score_id: UUID | None
    measure_index: int | None
    accuracy: float
    match: bool
    needs_replay: bool
    summary: str
    performance_feedback: dict[str, float]


class MusicMeasureHeatmapCell(BaseModel):
    """Measure-level aggregate for dashboard heatmap rendering."""

    measure_index: int
    attempts: int
    avg_accuracy: float
    replay_rate: float
    mismatch_rate: float


class MusicTeacherStudentDetailResponse(BaseModel):
    """Teacher-facing detail snapshot for one student."""

    user_id: str
    profile: MusicProgressSnapshotResponse
    recent_attempts: list[MusicPerformanceAttemptSummary]
    measure_heatmap: list[MusicMeasureHeatmapCell]
    assignments: list[MusicTeacherAssignmentResponse]


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


def _profile_overall_score(profile: MusicSkillProfile) -> float:
    return float(profile.overall_score or 0.0)


def _profile_rolling_metrics(profile: MusicSkillProfile) -> dict[str, float]:
    return {
        "pitchAccuracy": float(profile.pitch_score or 0.0),
        "rhythmAccuracy": float(profile.rhythm_score or 0.0),
        "tempoStability": float(profile.tempo_score or 0.0),
        "dynamicRange": float(profile.dynamics_score or 0.0),
        "articulationVariance": float(profile.articulation_score or 0.0),
    }


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _assignment_to_response(assignment: MusicLessonAssignment) -> MusicTeacherAssignmentResponse:
    return MusicTeacherAssignmentResponse(
        assignment_id=assignment.id,
        teacher_user_id=assignment.teacher_user_id,
        student_user_id=assignment.student_user_id,
        score_id=assignment.score_id,
        title=assignment.title,
        instructions=assignment.instructions or "",
        status=assignment.status or "ASSIGNED",
        target_measures=list(assignment.target_measures or []),
        due_at=_iso_or_none(assignment.due_at),
        created_at=_iso_or_none(assignment.created_at),
    )


def _attempt_to_summary(attempt: MusicPerformanceAttempt) -> MusicPerformanceAttemptSummary:
    return MusicPerformanceAttemptSummary(
        attempt_id=attempt.id,
        created_at=_iso_or_none(attempt.created_at),
        score_id=attempt.score_id,
        measure_index=attempt.measure_index,
        accuracy=round(float(attempt.accuracy or 0.0), 3),
        match=bool(attempt.match),
        needs_replay=bool(attempt.needs_replay),
        summary=attempt.summary or "",
        performance_feedback=dict(attempt.performance_feedback or {}),
    )


def _build_measure_heatmap(attempts: list[MusicPerformanceAttempt]) -> list[MusicMeasureHeatmapCell]:
    grouped: dict[int, list[MusicPerformanceAttempt]] = {}
    for attempt in attempts:
        if attempt.measure_index is None:
            continue
        grouped.setdefault(int(attempt.measure_index), []).append(attempt)

    cells: list[MusicMeasureHeatmapCell] = []
    for measure_index in sorted(grouped):
        rows = grouped[measure_index]
        attempt_count = len(rows)
        avg_accuracy = sum(float(row.accuracy or 0.0) for row in rows) / attempt_count
        replay_rate = sum(1 for row in rows if row.needs_replay) / attempt_count
        mismatch_rate = sum(1 for row in rows if not row.match) / attempt_count
        cells.append(
            MusicMeasureHeatmapCell(
                measure_index=measure_index,
                attempts=attempt_count,
                avg_accuracy=round(avg_accuracy, 3),
                replay_rate=round(replay_rate, 3),
                mismatch_rate=round(mismatch_rate, 3),
            )
        )
    return cells


def _build_progress_snapshot(user_id: str, profile: MusicSkillProfile | None) -> MusicProgressSnapshotResponse:
    if profile is None:
        return MusicProgressSnapshotResponse(
            user_id=user_id,
            has_profile=False,
            sample_count=0,
            weakest_dimension=None,
            consistency_score=0.0,
            practice_frequency=0.0,
            last_improvement_trend=0.0,
            overall_score=0.0,
            rolling_metrics={
                "pitchAccuracy": 0.0,
                "rhythmAccuracy": 0.0,
                "tempoStability": 0.0,
                "dynamicRange": 0.0,
                "articulationVariance": 0.0,
            },
        )

    return MusicProgressSnapshotResponse(
        user_id=profile.user_id,
        has_profile=True,
        sample_count=int(profile.sample_count or 0),
        weakest_dimension=profile.weakest_dimension,
        consistency_score=round(float(profile.consistency_score or 0.0), 3),
        practice_frequency=round(float(profile.practice_frequency or 0.0), 3),
        last_improvement_trend=round(float(profile.last_improvement_trend or 0.0), 3),
        overall_score=round(_profile_overall_score(profile), 3),
        rolling_metrics={k: round(v, 3) for k, v in _profile_rolling_metrics(profile).items()},
    )


def _record_performance_attempt(
    *,
    user_id: str,
    score_id: UUID,
    measure_index: int | None,
    instrument_profile: str,
    result,
) -> MusicPerformanceAttempt:
    return MusicPerformanceAttempt(
        user_id=user_id,
        score_id=score_id,
        measure_index=measure_index,
        instrument_profile=(instrument_profile or "AUTO").upper(),
        accuracy=float(result.accuracy),
        match=bool(result.match),
        needs_replay=bool(result.needs_replay),
        summary=result.summary,
        performance_feedback=result.performance_feedback,
    )


def _teacher_uid_allowlist() -> set[str]:
    raw = os.getenv("VISTA_TEACHER_UID_ALLOWLIST", "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _teacher_email_allowlist() -> set[str]:
    raw = os.getenv("VISTA_TEACHER_EMAIL_ALLOWLIST", "").strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _require_teacher_access(current_user: dict) -> None:
    uid = str(current_user.get("uid", "")).strip()
    email = str(current_user.get("email", "")).strip().lower()
    allowed_uid = uid and uid in _teacher_uid_allowlist()
    allowed_email = email and email in _teacher_email_allowlist()
    if not (allowed_uid or allowed_email):
        raise HTTPException(status_code=403, detail="Teacher access required.")


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
        instrument_profile=payload.instrument_profile,
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


@router.get("/analytics/me", response_model=MusicProgressSnapshotResponse)
async def get_music_progress_snapshot(
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicProgressSnapshotResponse:
    """Return the current user's deterministic adaptive progress snapshot."""
    query = await db.execute(select(MusicSkillProfile).where(MusicSkillProfile.user_id == current_user["uid"]))
    profile = query.scalar_one_or_none()
    return _build_progress_snapshot(current_user["uid"], profile)


@router.get("/analytics/teacher/students", response_model=MusicTeacherStudentsResponse)
async def list_teacher_students(
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicTeacherStudentsResponse:
    """Return teacher dashboard roster using adaptive profile snapshots."""
    _require_teacher_access(current_user)

    query = await db.execute(
        select(MusicSkillProfile).order_by(
            MusicSkillProfile.sample_count.desc(),
            MusicSkillProfile.updated_at.desc(),
        )
    )
    profiles = list(query.scalars().all())
    students = [
        MusicTeacherStudentSummary(
            user_id=profile.user_id,
            sample_count=int(profile.sample_count or 0),
            weakest_dimension=profile.weakest_dimension or "pitch",
            consistency_score=round(float(profile.consistency_score or 0.0), 3),
            practice_frequency=round(float(profile.practice_frequency or 0.0), 3),
            overall_score=round(_profile_overall_score(profile), 3),
            last_improvement_trend=round(float(profile.last_improvement_trend or 0.0), 3),
        )
        for profile in profiles
    ]
    return MusicTeacherStudentsResponse(students=students)


@router.post("/analytics/teacher/assignments", response_model=MusicTeacherAssignmentResponse)
async def create_teacher_assignment(
    payload: MusicTeacherAssignmentCreateRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicTeacherAssignmentResponse:
    """Create a teacher assignment for one student."""
    _require_teacher_access(current_user)
    teacher_uid = str(current_user.get("uid", "")).strip()
    if not teacher_uid:
        raise HTTPException(status_code=400, detail="Authenticated teacher uid is missing.")

    assignment = MusicLessonAssignment(
        teacher_user_id=teacher_uid,
        student_user_id=payload.student_user_id,
        score_id=payload.score_id,
        title=payload.title.strip(),
        instructions=(payload.instructions or "").strip(),
        status="ASSIGNED",
        target_measures=[int(item) for item in payload.target_measures if int(item) > 0],
        due_at=payload.due_at,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return _assignment_to_response(assignment)


@router.get("/analytics/teacher/assignments", response_model=MusicTeacherAssignmentsResponse)
async def list_teacher_assignments(
    student_user_id: str | None = None,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicTeacherAssignmentsResponse:
    """List assignments created by the current teacher."""
    _require_teacher_access(current_user)
    teacher_uid = str(current_user.get("uid", "")).strip()

    query = await db.execute(select(MusicLessonAssignment))
    all_assignments = list(query.scalars().all())
    filtered = [
        assignment
        for assignment in all_assignments
        if assignment.teacher_user_id == teacher_uid
        and (student_user_id is None or assignment.student_user_id == student_user_id)
    ]
    filtered.sort(key=lambda row: row.created_at or _EPOCH_UTC, reverse=True)
    return MusicTeacherAssignmentsResponse(assignments=[_assignment_to_response(item) for item in filtered])


@router.get("/analytics/teacher/students/{student_user_id}", response_model=MusicTeacherStudentDetailResponse)
async def get_teacher_student_detail(
    student_user_id: str,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicTeacherStudentDetailResponse:
    """Return student detail payload for teacher dashboard timelines + heatmaps."""
    _require_teacher_access(current_user)
    teacher_uid = str(current_user.get("uid", "")).strip()

    profile_query = await db.execute(select(MusicSkillProfile).where(MusicSkillProfile.user_id == student_user_id))
    profile = profile_query.scalar_one_or_none()
    snapshot = _build_progress_snapshot(student_user_id, profile)

    attempts_query = await db.execute(select(MusicPerformanceAttempt))
    student_attempts = [
        row for row in attempts_query.scalars().all() if row.user_id == student_user_id
    ]
    student_attempts.sort(key=lambda row: row.created_at or _EPOCH_UTC, reverse=True)
    recent_attempts = [_attempt_to_summary(row) for row in student_attempts[:30]]
    heatmap = _build_measure_heatmap(student_attempts)

    assignments_query = await db.execute(select(MusicLessonAssignment))
    assignments = [
        row
        for row in assignments_query.scalars().all()
        if row.teacher_user_id == teacher_uid and row.student_user_id == student_user_id
    ]
    assignments.sort(key=lambda row: row.created_at or _EPOCH_UTC, reverse=True)

    return MusicTeacherStudentDetailResponse(
        user_id=student_user_id,
        profile=snapshot,
        recent_attempts=recent_attempts,
        measure_heatmap=heatmap,
        assignments=[_assignment_to_response(item) for item in assignments],
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
        instrument_profile=payload.instrument_profile,
    )
    attempt = _record_performance_attempt(
        user_id=current_user["uid"],
        score_id=score.id,
        measure_index=payload.measure_index,
        instrument_profile=payload.instrument_profile,
        result=result,
    )
    db.add(attempt)
    await db.commit()
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
            instrument_profile=payload.instrument_profile,
        )
        attempt = _record_performance_attempt(
            user_id=current_user["uid"],
            score_id=score.id,
            measure_index=payload.current_measure_index,
            instrument_profile=payload.instrument_profile,
            result=result,
        )
        db.add(attempt)
        comparison = MusicPerformanceCompareResponse(
            score_id=score.id,
            **comparison_to_dict(result),
        )
        profile_payload, drill_payload, tutor_prompt = await update_user_skill_profile(
            db,
            user_id=current_user["uid"],
            instrument_profile=payload.instrument_profile,
            performance_feedback=result.performance_feedback,
        )
        return MusicLessonActionResponse(
            outcome="awaiting-compare" if result.needs_replay or not result.match else "reviewed",
            score=prepared_payload,
            comparison=comparison,
            user_skill_profile=profile_payload,
            next_drills=drill_payload,
            tutor_prompt=tutor_prompt,
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
