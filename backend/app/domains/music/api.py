"""Music API routes for Eurydice."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
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
from .models import (
    MusicChallengeAttempt,
    MusicCollaborationSession,
    MusicEngagementProfile,
    MusicLibraryItem,
    MusicLessonAssignment,
    MusicLessonPack,
    MusicLessonPackEntry,
    MusicLiveToolCall,
    MusicPerformanceAttempt,
    MusicScore,
    MusicSkillProfile,
)
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


class MusicLiveToolMetric(BaseModel):
    """Aggregated metric row for one live tool + source."""

    tool_name: str
    source: str
    total_calls: int
    successes: int
    failures: int
    success_rate: float
    avg_latency_ms: float
    last_called_at: str | None


class MusicLiveToolMetricsResponse(BaseModel):
    """User-scoped live tool reliability summary."""

    total_calls: int
    total_successes: int
    total_failures: int
    overall_success_rate: float
    metrics: list[MusicLiveToolMetric]


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


ChallengeModeLiteral = Literal["CALL_RESPONSE", "TEMPO_LADDER"]


class MusicChallengeRunRequest(BaseModel):
    """Request body for deterministic engagement challenge runs."""

    score_id: UUID
    mode: ChallengeModeLiteral
    audio_b64: str = Field(..., description="Base64-encoded mono PCM16 audio clip.")
    mime: str = Field("audio/pcm;rate=16000")
    measure_index: int | None = Field(None, ge=1)
    max_notes: int = Field(12, ge=1, le=12)
    instrument_profile: InstrumentProfileLiteral = Field("AUTO")
    target_tempo_bpm: float | None = Field(None, ge=30, le=260)
    tempo_tolerance_bpm: float = Field(8.0, ge=1, le=40)

    @field_validator("audio_b64")
    @classmethod
    def validate_audio_b64(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("audio_b64 is required.")
        return value


class MusicEngagementProfileResponse(BaseModel):
    """Gamification progress and completion-rate summary."""

    user_id: str
    practice_streak_days: int
    longest_streak_days: int
    total_challenge_attempts: int
    total_challenge_completions: int
    milestones: list[str]
    completion_rates: dict[str, float]


class MusicChallengeRunResponse(BaseModel):
    """Challenge execution payload."""

    attempt_id: UUID
    mode: ChallengeModeLiteral
    completed: bool
    completion_reason: str
    accuracy: float
    target_tempo_bpm: float | None
    played_tempo_bpm: float | None
    profile: MusicEngagementProfileResponse
    comparison: MusicPerformanceCompareResponse


class MusicChallengeTelemetryRow(BaseModel):
    """Per-mode challenge completion telemetry row."""

    mode: str
    attempts: int
    completions: int
    completion_rate: float


class MusicChallengeTelemetryResponse(BaseModel):
    """Challenge telemetry payload for analytics surfaces."""

    user_id: str
    total_attempts: int
    total_completions: int
    by_mode: list[MusicChallengeTelemetryRow]


class MusicCollaborationSessionCreateRequest(BaseModel):
    """Create collaboration session request."""

    score_id: UUID | None = None
    active_measure_index: int | None = Field(None, ge=1)
    target_phrase: str = Field("", max_length=1200)


class MusicCollaborationSyncRequest(BaseModel):
    """Sync request for active measure and target phrase."""

    active_measure_index: int | None = Field(None, ge=1)
    target_phrase: str | None = Field(None, max_length=1200)
    status: Literal["ACTIVE", "PAUSED", "ENDED"] | None = None


class MusicCollaborationSessionResponse(BaseModel):
    """Collaboration state payload."""

    session_id: UUID
    owner_user_id: str
    score_id: UUID | None
    active_measure_index: int | None
    target_phrase: str
    participants: list[str]
    status: str
    updated_at: str | None


LibraryContentTypeLiteral = Literal["EXERCISE", "REPERTOIRE", "THEORY", "ETUDE", "LESSON_FRAGMENT"]
LibraryDifficultyLiteral = Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"]


class MusicLibraryItemCreateRequest(BaseModel):
    """Create a library content item."""

    content_type: LibraryContentTypeLiteral
    title: str = Field(..., min_length=3, max_length=180)
    description: str = Field("", max_length=6000)
    instrument: str = Field("GENERAL", max_length=24)
    difficulty: LibraryDifficultyLiteral = "INTERMEDIATE"
    technique_tags: list[str] = Field(default_factory=list)
    learning_objective: str = Field("", max_length=200)
    source_format: Literal["NOTE_LINE", "MUSICXML", "MNX"] = "NOTE_LINE"
    source_text: str = Field("", max_length=20000)
    metadata: dict[str, object] = Field(default_factory=dict)
    curated: bool = False


class MusicLibraryItemResponse(BaseModel):
    """Library item payload."""

    item_id: UUID
    owner_user_id: str | None
    is_curated: bool
    content_type: str
    title: str
    description: str
    instrument: str
    difficulty: str
    technique_tags: list[str]
    learning_objective: str
    source_format: str
    source_text: str
    metadata: dict[str, object]
    created_at: str | None


class MusicLibraryListResponse(BaseModel):
    """Filtered library query payload."""

    items: list[MusicLibraryItemResponse]


class MusicLibraryRecommendationsResponse(BaseModel):
    """Adaptive content recommendation payload."""

    focus_dimension: str
    items: list[MusicLibraryItemResponse]
    recommendation_reason: str


class MusicLessonPackCreateRequest(BaseModel):
    """Create a lesson pack from ordered library item ids."""

    title: str = Field(..., min_length=3, max_length=180)
    description: str = Field("", max_length=6000)
    instrument: str = Field("GENERAL", max_length=24)
    difficulty: LibraryDifficultyLiteral = "INTERMEDIATE"
    tags: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    curated: bool = False
    item_ids: list[UUID] = Field(default_factory=list)
    item_expected_outcomes: list[str] = Field(default_factory=list)


class MusicLessonPackEntryResponse(BaseModel):
    """One ordered lesson pack entry."""

    entry_id: UUID
    sort_order: int
    item: MusicLibraryItemResponse
    expected_outcome: str


class MusicLessonPackResponse(BaseModel):
    """Lesson pack payload including ordered entries."""

    pack_id: UUID
    owner_user_id: str | None
    is_curated: bool
    title: str
    description: str
    instrument: str
    difficulty: str
    tags: list[str]
    expected_outcomes: list[str]
    status: str
    entries: list[MusicLessonPackEntryResponse]
    created_at: str | None


class MusicLessonPackListResponse(BaseModel):
    """Lesson pack list payload."""

    packs: list[MusicLessonPackResponse]


class MusicLessonPackLoadResponse(BaseModel):
    """Pack load payload suitable for direct guided lesson start."""

    pack: MusicLessonPackResponse
    selected_item_id: UUID
    score: MusicScorePrepareResponse
    lesson: MusicLessonStepResponse


class MusicLessonPackLoadRequest(BaseModel):
    """Select which pack entry to load into guided lesson."""

    entry_index: int = Field(1, ge=1)
    time_signature: str = Field("4/4")


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


def _ensure_milestones(profile: MusicEngagementProfile) -> list[str]:
    milestones = list(profile.milestones or [])
    def _add(label: str) -> None:
        if label not in milestones:
            milestones.append(label)

    if int(profile.total_challenge_completions or 0) >= 1:
        _add("first-challenge-completed")
    if int(profile.practice_streak_days or 0) >= 3:
        _add("three-day-streak")
    if int(profile.total_challenge_completions or 0) >= 10:
        _add("ten-challenges-completed")
    return milestones


def _update_streak(profile: MusicEngagementProfile, activity_day: date) -> None:
    previous_day = profile.last_activity_date
    if previous_day is None:
        profile.practice_streak_days = 1
    else:
        delta_days = (activity_day - previous_day).days
        if delta_days == 0:
            profile.practice_streak_days = max(1, int(profile.practice_streak_days or 0))
        elif delta_days == 1:
            profile.practice_streak_days = int(profile.practice_streak_days or 0) + 1
        else:
            profile.practice_streak_days = 1
    profile.longest_streak_days = max(
        int(profile.longest_streak_days or 0),
        int(profile.practice_streak_days or 0),
    )
    profile.last_activity_date = activity_day
    profile.milestones = _ensure_milestones(profile)


def _engagement_profile_response(
    user_id: str,
    profile: MusicEngagementProfile | None,
    completion_rates: dict[str, float],
) -> MusicEngagementProfileResponse:
    if profile is None:
        return MusicEngagementProfileResponse(
            user_id=user_id,
            practice_streak_days=0,
            longest_streak_days=0,
            total_challenge_attempts=0,
            total_challenge_completions=0,
            milestones=[],
            completion_rates={key: round(value, 3) for key, value in completion_rates.items()},
        )
    return MusicEngagementProfileResponse(
        user_id=user_id,
        practice_streak_days=int(profile.practice_streak_days or 0),
        longest_streak_days=int(profile.longest_streak_days or 0),
        total_challenge_attempts=int(profile.total_challenge_attempts or 0),
        total_challenge_completions=int(profile.total_challenge_completions or 0),
        milestones=list(profile.milestones or []),
        completion_rates={key: round(value, 3) for key, value in completion_rates.items()},
    )


def _collab_to_response(session: MusicCollaborationSession) -> MusicCollaborationSessionResponse:
    return MusicCollaborationSessionResponse(
        session_id=session.id,
        owner_user_id=session.owner_user_id,
        score_id=session.score_id,
        active_measure_index=session.active_measure_index,
        target_phrase=session.target_phrase or "",
        participants=list(session.participants or []),
        status=session.status or "ACTIVE",
        updated_at=_iso_or_none(session.updated_at),
    )


def _completion_rates_for_attempts(attempts: list[MusicChallengeAttempt]) -> dict[str, float]:
    grouped: dict[str, list[MusicChallengeAttempt]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt.mode or "UNKNOWN", []).append(attempt)
    rates: dict[str, float] = {}
    for mode, rows in grouped.items():
        if not rows:
            rates[mode] = 0.0
            continue
        completion_rate = sum(1 for row in rows if row.completed) / len(rows)
        rates[mode] = round(completion_rate, 3)
    return rates


def _challenge_completed(
    *,
    mode: ChallengeModeLiteral,
    result,
    target_tempo_bpm: float | None,
    tempo_tolerance_bpm: float,
) -> tuple[bool, str, float | None]:
    played_tempo = None
    if isinstance(result.played_phrase, dict):
        tempo_value = result.played_phrase.get("tempo_bpm")
        if tempo_value is not None:
            played_tempo = float(tempo_value)

    if mode == "CALL_RESPONSE":
        completed = bool(result.match) and not result.needs_replay and float(result.accuracy) >= 0.85
        if completed:
            return True, "Call-response matched with confident timing and pitch.", played_tempo
        return False, "Call-response needs cleaner replay or tighter alignment.", played_tempo

    tempo_target = target_tempo_bpm or 120.0
    tempo_ok = played_tempo is not None and abs(played_tempo - tempo_target) <= tempo_tolerance_bpm
    completed = (not result.needs_replay) and float(result.accuracy) >= 0.75 and tempo_ok
    if completed:
        return True, "Tempo ladder passed with target-tempo control.", played_tempo
    return False, "Tempo ladder incomplete: tighten tempo lock and replay clarity.", played_tempo


async def _get_or_create_engagement_profile(db: AsyncSession, user_id: str) -> MusicEngagementProfile:
    query = await db.execute(select(MusicEngagementProfile).where(MusicEngagementProfile.user_id == user_id))
    profile = query.scalar_one_or_none()
    if profile is not None:
        return profile
    profile = MusicEngagementProfile(user_id=user_id, milestones=[])
    db.add(profile)
    return profile


async def _get_collaboration_session(db: AsyncSession, session_id: UUID) -> MusicCollaborationSession:
    query = await db.execute(select(MusicCollaborationSession).where(MusicCollaborationSession.id == session_id))
    session = query.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Collaboration session not found.")
    return session


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


def _has_teacher_access(current_user: dict) -> bool:
    uid = str(current_user.get("uid", "")).strip()
    email = str(current_user.get("email", "")).strip().lower()
    allowed_uid = uid and uid in _teacher_uid_allowlist()
    allowed_email = email and email in _teacher_email_allowlist()
    return bool(allowed_uid or allowed_email)


def _require_teacher_access(current_user: dict) -> None:
    if not _has_teacher_access(current_user):
        raise HTTPException(status_code=403, detail="Teacher access required.")


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower().replace("_", "-")


def _library_item_visible(item: MusicLibraryItem, user_id: str) -> bool:
    if bool(item.is_curated):
        return True
    return (item.owner_user_id or "") == user_id


def _to_library_item_response(item: MusicLibraryItem) -> MusicLibraryItemResponse:
    return MusicLibraryItemResponse(
        item_id=item.id,
        owner_user_id=item.owner_user_id,
        is_curated=bool(item.is_curated),
        content_type=item.content_type,
        title=item.title,
        description=item.description or "",
        instrument=item.instrument,
        difficulty=item.difficulty,
        technique_tags=list(item.technique_tags or []),
        learning_objective=item.learning_objective or "",
        source_format=item.source_format,
        source_text=item.source_text or "",
        metadata=dict(item.metadata_json or {}),
        created_at=_iso_or_none(item.created_at),
    )


def _pack_visible(pack: MusicLessonPack, user_id: str) -> bool:
    if bool(pack.is_curated):
        return True
    return (pack.owner_user_id or "") == user_id


def _to_pack_response(
    pack: MusicLessonPack,
    *,
    entries: list[MusicLessonPackEntry],
    item_by_id: dict[UUID, MusicLibraryItem],
) -> MusicLessonPackResponse:
    sorted_entries = sorted(entries, key=lambda entry: int(entry.sort_order or 0))
    entry_payloads: list[MusicLessonPackEntryResponse] = []
    for entry in sorted_entries:
        item = item_by_id.get(entry.item_id)
        if item is None:
            continue
        entry_payloads.append(
            MusicLessonPackEntryResponse(
                entry_id=entry.id,
                sort_order=int(entry.sort_order or 0),
                item=_to_library_item_response(item),
                expected_outcome=entry.expected_outcome or "",
            )
        )
    return MusicLessonPackResponse(
        pack_id=pack.id,
        owner_user_id=pack.owner_user_id,
        is_curated=bool(pack.is_curated),
        title=pack.title,
        description=pack.description or "",
        instrument=pack.instrument,
        difficulty=pack.difficulty,
        tags=list(pack.tags or []),
        expected_outcomes=list(pack.expected_outcomes or []),
        status=pack.status or "ACTIVE",
        entries=entry_payloads,
        created_at=_iso_or_none(pack.created_at),
    )


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


@router.get("/analytics/live-tools", response_model=MusicLiveToolMetricsResponse)
async def live_tool_metrics(
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLiveToolMetricsResponse:
    """Return user-scoped success/failure telemetry for deterministic live tools."""
    result = await db.execute(
        select(MusicLiveToolCall)
        .where(MusicLiveToolCall.user_id == current_user["uid"])
        .order_by(MusicLiveToolCall.created_at.desc())
        .limit(1000)
    )
    rows = list(result.scalars().all())
    if not rows:
        return MusicLiveToolMetricsResponse(
            total_calls=0,
            total_successes=0,
            total_failures=0,
            overall_success_rate=0.0,
            metrics=[],
        )

    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = ((row.tool_name or "unknown").lower(), (row.source or "client").lower())
        bucket = grouped.setdefault(
            key,
            {
                "tool_name": key[0],
                "source": key[1],
                "total_calls": 0,
                "successes": 0,
                "failures": 0,
                "latency_sum": 0,
                "latency_count": 0,
                "last_called_at": None,
            },
        )
        bucket["total_calls"] = int(bucket["total_calls"]) + 1
        if (row.status or "").upper() == "SUCCESS":
            bucket["successes"] = int(bucket["successes"]) + 1
        else:
            bucket["failures"] = int(bucket["failures"]) + 1
        if row.latency_ms is not None:
            bucket["latency_sum"] = int(bucket["latency_sum"]) + int(row.latency_ms)
            bucket["latency_count"] = int(bucket["latency_count"]) + 1
        if bucket["last_called_at"] is None:
            bucket["last_called_at"] = _iso_or_none(row.created_at)

    metrics = [
        MusicLiveToolMetric(
            tool_name=str(bucket["tool_name"]),
            source=str(bucket["source"]),
            total_calls=int(bucket["total_calls"]),
            successes=int(bucket["successes"]),
            failures=int(bucket["failures"]),
            success_rate=round(
                int(bucket["successes"]) / max(1, int(bucket["total_calls"])),
                3,
            ),
            avg_latency_ms=round(
                int(bucket["latency_sum"]) / max(1, int(bucket["latency_count"])),
                1,
            ),
            last_called_at=bucket["last_called_at"],
        )
        for bucket in grouped.values()
    ]
    metrics.sort(key=lambda item: (-item.total_calls, item.tool_name, item.source))

    total_calls = len(rows)
    total_successes = sum(1 for row in rows if (row.status or "").upper() == "SUCCESS")
    total_failures = total_calls - total_successes

    return MusicLiveToolMetricsResponse(
        total_calls=total_calls,
        total_successes=total_successes,
        total_failures=total_failures,
        overall_success_rate=round(total_successes / max(1, total_calls), 3),
        metrics=metrics,
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


@router.post("/library/items", response_model=MusicLibraryItemResponse)
async def create_library_item(
    payload: MusicLibraryItemCreateRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLibraryItemResponse:
    """Create one content library item (curated or user-generated)."""
    is_teacher = _has_teacher_access(current_user)
    if payload.curated and not is_teacher:
        raise HTTPException(status_code=403, detail="Teacher access required for curated library items.")

    tags = sorted({_normalize_tag(tag) for tag in payload.technique_tags if tag.strip()})
    item = MusicLibraryItem(
        owner_user_id=current_user["uid"],
        is_curated=bool(payload.curated and is_teacher),
        content_type=payload.content_type,
        title=payload.title.strip(),
        description=(payload.description or "").strip(),
        instrument=(payload.instrument or "GENERAL").strip().upper(),
        difficulty=payload.difficulty,
        technique_tags=tags,
        learning_objective=(payload.learning_objective or "").strip(),
        source_format=payload.source_format,
        source_text=(payload.source_text or "").strip(),
        metadata_json=dict(payload.metadata or {}),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _to_library_item_response(item)


@router.get("/library/items", response_model=MusicLibraryListResponse)
async def list_library_items(
    instrument: str | None = None,
    difficulty: str | None = None,
    technique: str | None = None,
    content_type: str | None = None,
    include_private: bool = True,
    limit: int = 50,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLibraryListResponse:
    """List library content with filtering by instrument/difficulty/technique/type."""
    safe_limit = max(1, min(200, int(limit)))
    query = await db.execute(select(MusicLibraryItem))
    items = list(query.scalars().all())
    user_id = current_user["uid"]

    instrument_filter = (instrument or "").strip().upper()
    difficulty_filter = (difficulty or "").strip().upper()
    type_filter = (content_type or "").strip().upper()
    technique_filter = _normalize_tag(technique) if (technique or "").strip() else ""

    filtered: list[MusicLibraryItem] = []
    for item in items:
        visible = _library_item_visible(item, user_id)
        if not visible:
            continue
        if not include_private and not bool(item.is_curated):
            continue
        if instrument_filter and item.instrument.upper() != instrument_filter:
            continue
        if difficulty_filter and item.difficulty.upper() != difficulty_filter:
            continue
        if type_filter and item.content_type.upper() != type_filter:
            continue
        if technique_filter:
            tags = {_normalize_tag(tag) for tag in (item.technique_tags or [])}
            if technique_filter not in tags:
                continue
        filtered.append(item)

    filtered.sort(
        key=lambda row: (
            0 if row.is_curated else 1,
            -(row.created_at.timestamp() if row.created_at else 0),
        )
    )
    return MusicLibraryListResponse(items=[_to_library_item_response(row) for row in filtered[:safe_limit]])


@router.get("/library/recommendations/me", response_model=MusicLibraryRecommendationsResponse)
async def recommend_library_items_for_user(
    limit: int = 6,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLibraryRecommendationsResponse:
    """Recommend library items using adaptive profile metadata."""
    safe_limit = max(1, min(20, int(limit)))
    profile_query = await db.execute(select(MusicSkillProfile).where(MusicSkillProfile.user_id == current_user["uid"]))
    profile = profile_query.scalar_one_or_none()
    focus_dimension = (profile.weakest_dimension if profile is not None else "pitch") or "pitch"

    dimension_tags: dict[str, set[str]] = {
        "pitch": {"intonation", "intervals", "ear-training"},
        "rhythm": {"rhythm", "subdivision", "timing", "groove"},
        "tempo": {"tempo", "timing", "metronome"},
        "dynamics": {"dynamics", "expression", "control"},
        "articulation": {"articulation", "phrasing", "staccato", "legato"},
    }
    target_tags = dimension_tags.get(focus_dimension, {"timing"})

    item_query = await db.execute(select(MusicLibraryItem))
    visible_items = [
        item
        for item in item_query.scalars().all()
        if _library_item_visible(item, current_user["uid"])
    ]

    tagged_matches: list[MusicLibraryItem] = []
    fallback_matches: list[MusicLibraryItem] = []
    for item in visible_items:
        tags = {_normalize_tag(tag) for tag in (item.technique_tags or [])}
        if tags.intersection(target_tags):
            tagged_matches.append(item)
            continue
        objective = (item.learning_objective or "").lower()
        if focus_dimension in objective:
            fallback_matches.append(item)

    candidates = tagged_matches or fallback_matches or visible_items
    candidates.sort(
        key=lambda row: (
            0 if row.is_curated else 1,
            0 if row.difficulty.upper() == "BEGINNER" else 1 if row.difficulty.upper() == "INTERMEDIATE" else 2,
            -(row.created_at.timestamp() if row.created_at else 0),
        )
    )

    return MusicLibraryRecommendationsResponse(
        focus_dimension=focus_dimension,
        recommendation_reason=(
            f"Recommendations target your weakest dimension: {focus_dimension}. "
            "Items are ranked by technique-tag alignment and content visibility."
        ),
        items=[_to_library_item_response(item) for item in candidates[:safe_limit]],
    )


@router.post("/library/packs", response_model=MusicLessonPackResponse)
async def create_lesson_pack(
    payload: MusicLessonPackCreateRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLessonPackResponse:
    """Create one ordered lesson pack from library items."""
    is_teacher = _has_teacher_access(current_user)
    if payload.curated and not is_teacher:
        raise HTTPException(status_code=403, detail="Teacher access required for curated lesson packs.")
    if not payload.item_ids:
        raise HTTPException(status_code=400, detail="item_ids is required to create a lesson pack.")

    item_query = await db.execute(select(MusicLibraryItem))
    item_by_id = {item.id: item for item in item_query.scalars().all()}
    for item_id in payload.item_ids:
        item = item_by_id.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Library item not found: {item_id}")
        if not _library_item_visible(item, current_user["uid"]):
            raise HTTPException(status_code=403, detail=f"Not authorised to use library item: {item_id}")

    pack = MusicLessonPack(
        owner_user_id=current_user["uid"],
        is_curated=bool(payload.curated and is_teacher),
        title=payload.title.strip(),
        description=(payload.description or "").strip(),
        instrument=(payload.instrument or "GENERAL").strip().upper(),
        difficulty=payload.difficulty,
        tags=sorted({_normalize_tag(tag) for tag in payload.tags if tag.strip()}),
        expected_outcomes=[item.strip() for item in payload.expected_outcomes if item.strip()],
        status="ACTIVE",
    )
    db.add(pack)
    await db.commit()
    await db.refresh(pack)

    entries: list[MusicLessonPackEntry] = []
    for index, item_id in enumerate(payload.item_ids):
        expected_outcome = payload.item_expected_outcomes[index] if index < len(payload.item_expected_outcomes) else ""
        entry = MusicLessonPackEntry(
            pack_id=pack.id,
            item_id=item_id,
            sort_order=index + 1,
            expected_outcome=(expected_outcome or "").strip(),
        )
        db.add(entry)
        entries.append(entry)
    await db.commit()

    return _to_pack_response(pack, entries=entries, item_by_id=item_by_id)


@router.get("/library/packs", response_model=MusicLessonPackListResponse)
async def list_lesson_packs(
    instrument: str | None = None,
    difficulty: str | None = None,
    tag: str | None = None,
    include_private: bool = True,
    limit: int = 50,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLessonPackListResponse:
    """List lesson packs with filtering and visibility controls."""
    safe_limit = max(1, min(200, int(limit)))
    pack_query = await db.execute(select(MusicLessonPack))
    packs = list(pack_query.scalars().all())
    entry_query = await db.execute(select(MusicLessonPackEntry))
    entries = list(entry_query.scalars().all())
    item_query = await db.execute(select(MusicLibraryItem))
    item_by_id = {item.id: item for item in item_query.scalars().all()}

    entries_by_pack: dict[UUID, list[MusicLessonPackEntry]] = {}
    for entry in entries:
        entries_by_pack.setdefault(entry.pack_id, []).append(entry)

    instrument_filter = (instrument or "").strip().upper()
    difficulty_filter = (difficulty or "").strip().upper()
    tag_filter = _normalize_tag(tag) if (tag or "").strip() else ""

    visible_packs: list[MusicLessonPack] = []
    for pack in packs:
        if not _pack_visible(pack, current_user["uid"]):
            continue
        if not include_private and not bool(pack.is_curated):
            continue
        if instrument_filter and pack.instrument.upper() != instrument_filter:
            continue
        if difficulty_filter and pack.difficulty.upper() != difficulty_filter:
            continue
        if tag_filter:
            tags = {_normalize_tag(item) for item in (pack.tags or [])}
            if tag_filter not in tags:
                continue
        visible_packs.append(pack)

    visible_packs.sort(
        key=lambda row: (
            0 if row.is_curated else 1,
            -(row.created_at.timestamp() if row.created_at else 0),
        )
    )
    payload = [
        _to_pack_response(pack, entries=entries_by_pack.get(pack.id, []), item_by_id=item_by_id)
        for pack in visible_packs[:safe_limit]
    ]
    return MusicLessonPackListResponse(packs=payload)


@router.post("/library/packs/{pack_id}/load", response_model=MusicLessonPackLoadResponse)
async def load_lesson_pack_into_guided_flow(
    pack_id: UUID,
    payload: MusicLessonPackLoadRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicLessonPackLoadResponse:
    """Load one lesson pack entry directly into guided lesson workflow."""
    pack_query = await db.execute(select(MusicLessonPack).where(MusicLessonPack.id == pack_id))
    pack = pack_query.scalar_one_or_none()
    if pack is None:
        raise HTTPException(status_code=404, detail="Lesson pack not found.")
    if not _pack_visible(pack, current_user["uid"]):
        raise HTTPException(status_code=403, detail="Not authorised to access this lesson pack.")

    entry_query = await db.execute(select(MusicLessonPackEntry))
    all_entries = [entry for entry in entry_query.scalars().all() if entry.pack_id == pack.id]
    all_entries.sort(key=lambda row: int(row.sort_order or 0))
    if not all_entries:
        raise HTTPException(status_code=400, detail="Lesson pack has no entries.")
    if payload.entry_index > len(all_entries):
        raise HTTPException(status_code=400, detail="entry_index exceeds lesson pack length.")

    selected_entry = all_entries[payload.entry_index - 1]
    item_query = await db.execute(select(MusicLibraryItem))
    item_by_id = {item.id: item for item in item_query.scalars().all()}
    selected_item = item_by_id.get(selected_entry.item_id)
    if selected_item is None:
        raise HTTPException(status_code=404, detail="Selected lesson item no longer exists.")
    if selected_item.source_format.upper() != "NOTE_LINE":
        raise HTTPException(status_code=400, detail="Only NOTE_LINE lesson items can be loaded into guided workflow today.")
    source_text = (selected_item.source_text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="Selected lesson item has no source_text.")

    time_signature = (
        str((selected_item.metadata_json or {}).get("time_signature", "")).strip()
        or payload.time_signature
        or "4/4"
    )
    imported = import_simple_score(source_text, time_signature=time_signature)
    stored_score = MusicScore(
        user_id=current_user["uid"],
        source_format=imported.format,
        time_signature=time_signature,
        note_count=imported.note_count,
        normalized=imported.normalized,
        summary=imported.summary,
        warnings=list(imported.warnings),
        measures=score_to_dict(imported)["measures"],
    )
    db.add(stored_score)
    await db.commit()
    await db.refresh(stored_score)

    prepared_score = _prepare_music_score_payload(imported, stored_score, time_signature)
    lesson_step = _build_lesson_step_from_score(
        stored_score,
        MusicLessonStepRequest(current_measure_index=None, lesson_stage="idle"),
    )
    pack_payload = _to_pack_response(pack, entries=all_entries, item_by_id=item_by_id)
    return MusicLessonPackLoadResponse(
        pack=pack_payload,
        selected_item_id=selected_item.id,
        score=prepared_score,
        lesson=lesson_step,
    )


@router.get("/engagement/me", response_model=MusicEngagementProfileResponse)
async def get_engagement_profile(
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicEngagementProfileResponse:
    """Return engagement streak/milestone state and challenge completion rates."""
    profile_query = await db.execute(select(MusicEngagementProfile).where(MusicEngagementProfile.user_id == current_user["uid"]))
    profile = profile_query.scalar_one_or_none()

    attempts_query = await db.execute(select(MusicChallengeAttempt))
    attempts = [row for row in attempts_query.scalars().all() if row.user_id == current_user["uid"]]
    completion_rates = _completion_rates_for_attempts(attempts)
    return _engagement_profile_response(current_user["uid"], profile, completion_rates)


@router.get("/engagement/telemetry", response_model=MusicChallengeTelemetryResponse)
async def get_engagement_telemetry(
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicChallengeTelemetryResponse:
    """Return per-mode challenge completion telemetry for the current user."""
    attempts_query = await db.execute(select(MusicChallengeAttempt))
    attempts = [row for row in attempts_query.scalars().all() if row.user_id == current_user["uid"]]

    grouped: dict[str, list[MusicChallengeAttempt]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt.mode or "UNKNOWN", []).append(attempt)

    by_mode: list[MusicChallengeTelemetryRow] = []
    for mode in sorted(grouped):
        rows = grouped[mode]
        attempt_count = len(rows)
        completion_count = sum(1 for row in rows if row.completed)
        by_mode.append(
            MusicChallengeTelemetryRow(
                mode=mode,
                attempts=attempt_count,
                completions=completion_count,
                completion_rate=round(completion_count / attempt_count, 3) if attempt_count else 0.0,
            )
        )

    return MusicChallengeTelemetryResponse(
        user_id=current_user["uid"],
        total_attempts=len(attempts),
        total_completions=sum(1 for row in attempts if row.completed),
        by_mode=by_mode,
    )


@router.post("/engagement/challenges/run", response_model=MusicChallengeRunResponse)
async def run_engagement_challenge(
    payload: MusicChallengeRunRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicChallengeRunResponse:
    """Run one deterministic challenge mode against a lesson bar."""
    score = await _get_owned_score(db, payload.score_id, current_user["uid"])
    compare_score = _build_compare_score(score, payload.measure_index)

    sample_rate = parse_pcm_mime(payload.mime)
    audio_bytes = decode_audio_b64(payload.audio_b64)
    comparison_result = compare_performance_against_score(
        compare_score,
        audio_bytes=audio_bytes,
        sample_rate=sample_rate,
        max_notes=payload.max_notes,
        instrument_profile=payload.instrument_profile,
    )
    comparison_payload = MusicPerformanceCompareResponse(
        score_id=score.id,
        **comparison_to_dict(comparison_result),
    )

    completed, completion_reason, played_tempo = _challenge_completed(
        mode=payload.mode,
        result=comparison_result,
        target_tempo_bpm=payload.target_tempo_bpm,
        tempo_tolerance_bpm=payload.tempo_tolerance_bpm,
    )

    challenge_attempt = MusicChallengeAttempt(
        user_id=current_user["uid"],
        score_id=score.id,
        measure_index=payload.measure_index,
        mode=payload.mode,
        instrument_profile=payload.instrument_profile,
        target_tempo_bpm=payload.target_tempo_bpm,
        played_tempo_bpm=played_tempo,
        accuracy=float(comparison_result.accuracy),
        completed=completed,
        completion_reason=completion_reason,
        needs_replay=bool(comparison_result.needs_replay),
    )
    db.add(challenge_attempt)

    profile = await _get_or_create_engagement_profile(db, current_user["uid"])
    profile.total_challenge_attempts = int(profile.total_challenge_attempts or 0) + 1
    if completed:
        profile.total_challenge_completions = int(profile.total_challenge_completions or 0) + 1
    _update_streak(profile, datetime.now(timezone.utc).date())
    db.add(profile)

    await db.commit()
    await db.refresh(challenge_attempt)
    await db.refresh(profile)

    attempts_query = await db.execute(select(MusicChallengeAttempt))
    attempts = [row for row in attempts_query.scalars().all() if row.user_id == current_user["uid"]]
    completion_rates = _completion_rates_for_attempts(attempts)
    profile_payload = _engagement_profile_response(current_user["uid"], profile, completion_rates)

    return MusicChallengeRunResponse(
        attempt_id=challenge_attempt.id,
        mode=payload.mode,
        completed=completed,
        completion_reason=completion_reason,
        accuracy=round(float(comparison_result.accuracy), 3),
        target_tempo_bpm=payload.target_tempo_bpm,
        played_tempo_bpm=played_tempo,
        profile=profile_payload,
        comparison=comparison_payload,
    )


@router.post("/engagement/collaboration/sessions", response_model=MusicCollaborationSessionResponse)
async def create_collaboration_session(
    payload: MusicCollaborationSessionCreateRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicCollaborationSessionResponse:
    """Create a collaboration session anchored to score state."""
    if payload.score_id is not None:
        await _get_owned_score(db, payload.score_id, current_user["uid"])

    owner_uid = current_user["uid"]
    session = MusicCollaborationSession(
        owner_user_id=owner_uid,
        score_id=payload.score_id,
        active_measure_index=payload.active_measure_index,
        target_phrase=(payload.target_phrase or "").strip(),
        participants=[owner_uid],
        status="ACTIVE",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _collab_to_response(session)


@router.post("/engagement/collaboration/sessions/{session_id}/join", response_model=MusicCollaborationSessionResponse)
async def join_collaboration_session(
    session_id: UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicCollaborationSessionResponse:
    """Join an existing collaboration session as participant."""
    session = await _get_collaboration_session(db, session_id)
    participants = list(session.participants or [])
    if current_user["uid"] not in participants:
        participants.append(current_user["uid"])
        session.participants = participants
        db.add(session)
        await db.commit()
        await db.refresh(session)
    return _collab_to_response(session)


@router.get("/engagement/collaboration/sessions/{session_id}", response_model=MusicCollaborationSessionResponse)
async def get_collaboration_session(
    session_id: UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicCollaborationSessionResponse:
    """Fetch shared collaboration score state for participants."""
    session = await _get_collaboration_session(db, session_id)
    participants = list(session.participants or [])
    if current_user["uid"] != session.owner_user_id and current_user["uid"] not in participants:
        raise HTTPException(status_code=403, detail="Not authorised for this collaboration session.")
    return _collab_to_response(session)


@router.post("/engagement/collaboration/sessions/{session_id}/sync", response_model=MusicCollaborationSessionResponse)
async def sync_collaboration_session(
    session_id: UUID,
    payload: MusicCollaborationSyncRequest,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MusicCollaborationSessionResponse:
    """Synchronize active measure and target phrase for collaboration session."""
    session = await _get_collaboration_session(db, session_id)
    participants = list(session.participants or [])
    if current_user["uid"] != session.owner_user_id and current_user["uid"] not in participants:
        raise HTTPException(status_code=403, detail="Not authorised for this collaboration session.")

    if payload.active_measure_index is not None:
        session.active_measure_index = payload.active_measure_index
    if payload.target_phrase is not None:
        session.target_phrase = payload.target_phrase.strip()
    if payload.status is not None:
        session.status = payload.status
    if current_user["uid"] not in participants:
        participants.append(current_user["uid"])
    session.participants = participants

    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _collab_to_response(session)


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
