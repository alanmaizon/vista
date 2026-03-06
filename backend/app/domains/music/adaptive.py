"""Deterministic adaptive profile + drill recommendations for Eurydice."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MusicSkillProfile

DimensionKey = Literal["pitch", "rhythm", "tempo", "dynamics", "articulation"]
DrillDifficulty = Literal["foundation", "intermediate", "advanced"]

_DIMENSION_TO_FEEDBACK_KEY: dict[DimensionKey, str] = {
    "pitch": "pitchAccuracy",
    "rhythm": "rhythmAccuracy",
    "tempo": "tempoStability",
    "dynamics": "dynamicRange",
    "articulation": "articulationVariance",
}

_OVERALL_WEIGHTS: dict[DimensionKey, float] = {
    "pitch": 0.35,
    "rhythm": 0.25,
    "tempo": 0.2,
    "dynamics": 0.1,
    "articulation": 0.1,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_signed(value: float, limit: float = 1.0) -> float:
    return max(-limit, min(limit, value))


def _round3(value: float) -> float:
    return round(value, 3)


def _as_float(value: float | None, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _extract_metrics(performance_feedback: dict[str, float]) -> dict[DimensionKey, float]:
    metrics: dict[DimensionKey, float] = {}
    for dimension, feedback_key in _DIMENSION_TO_FEEDBACK_KEY.items():
        raw = performance_feedback.get(feedback_key, 0.0)
        metrics[dimension] = _clamp01(float(raw))
    return metrics


def _overall_score(metrics: dict[DimensionKey, float]) -> float:
    total = 0.0
    for dimension, weight in _OVERALL_WEIGHTS.items():
        total += metrics[dimension] * weight
    return _clamp01(total)


def _profile_metrics(profile: MusicSkillProfile) -> dict[DimensionKey, float]:
    return {
        "pitch": _clamp01(_as_float(profile.pitch_score)),
        "rhythm": _clamp01(_as_float(profile.rhythm_score)),
        "tempo": _clamp01(_as_float(profile.tempo_score)),
        "dynamics": _clamp01(_as_float(profile.dynamics_score)),
        "articulation": _clamp01(_as_float(profile.articulation_score)),
    }


def _difficulty_for_profile(profile: MusicSkillProfile) -> DrillDifficulty:
    if profile.sample_count < 5 or profile.consistency_score < 0.55:
        return "foundation"
    if profile.sample_count < 20 or profile.consistency_score < 0.8:
        return "intermediate"
    return "advanced"


def _make_drill(
    *,
    drill_id: str,
    title: str,
    focus_dimension: DimensionKey,
    rationale: str,
    instructions: str,
    difficulty: DrillDifficulty,
    current_score: float,
) -> dict[str, object]:
    return {
        "id": drill_id,
        "title": title,
        "focus_dimension": focus_dimension,
        "rationale": rationale,
        "instructions": instructions,
        "difficulty": difficulty,
        "target_score": _round3(min(0.98, current_score + 0.12)),
    }


def _drills_for_dimension(
    dimension: DimensionKey,
    *,
    difficulty: DrillDifficulty,
    current_score: float,
) -> list[dict[str, object]]:
    if dimension == "pitch":
        return [
            _make_drill(
                drill_id="pitch-slow-ladder",
                title="Pitch ladder replay",
                focus_dimension=dimension,
                rationale="Pitch stability is currently your lowest metric.",
                instructions="Play a 5-note ladder slowly with tuner feedback, then repeat without visual aid.",
                difficulty=difficulty,
                current_score=current_score,
            ),
            _make_drill(
                drill_id="pitch-anchor-drone",
                title="Drone anchoring",
                focus_dimension=dimension,
                rationale="Anchoring intervals to a fixed tonic improves intonation transfer.",
                instructions="Sustain tonic drone and sing/play thirds and fifths against it in two octaves.",
                difficulty=difficulty,
                current_score=current_score,
            ),
        ]
    if dimension == "rhythm":
        return [
            _make_drill(
                drill_id="rhythm-subdivision-clap",
                title="Subdivision clap",
                focus_dimension=dimension,
                rationale="Rhythm alignment is lagging relative to other dimensions.",
                instructions="Clap and count 8 bars with metronome subdivisions before replaying the phrase.",
                difficulty=difficulty,
                current_score=current_score,
            ),
            _make_drill(
                drill_id="rhythm-accent-grid",
                title="Accent grid practice",
                focus_dimension=dimension,
                rationale="Consistent accents improve internal pulse and phrase alignment.",
                instructions="Repeat one bar and accent beat 1, then beat 2, then off-beats.",
                difficulty=difficulty,
                current_score=current_score,
            ),
        ]
    if dimension == "tempo":
        return [
            _make_drill(
                drill_id="tempo-ladder",
                title="Tempo ladder",
                focus_dimension=dimension,
                rationale="Tempo stability needs tighter onset control.",
                instructions="Run the same bar at 60, 72, 84 BPM and return to 60 BPM without drift.",
                difficulty=difficulty,
                current_score=current_score,
            ),
            _make_drill(
                drill_id="tempo-gap-check",
                title="Gap timing check",
                focus_dimension=dimension,
                rationale="Onset drift is creating comparison mismatch risk.",
                instructions="Play two notes with fixed rests and verify each rest length against a click.",
                difficulty=difficulty,
                current_score=current_score,
            ),
        ]
    if dimension == "dynamics":
        return [
            _make_drill(
                drill_id="dynamics-crescendo-decrescendo",
                title="Dynamic arc drill",
                focus_dimension=dimension,
                rationale="Dynamic control can be widened for clearer expressive contrast.",
                instructions="Play one phrase pp->ff->pp while preserving pitch and rhythm accuracy.",
                difficulty=difficulty,
                current_score=current_score,
            ),
            _make_drill(
                drill_id="dynamics-step-levels",
                title="Volume step levels",
                focus_dimension=dimension,
                rationale="Stable level transitions improve expressive precision.",
                instructions="Repeat the same bar at 4 fixed dynamic levels with clean transitions.",
                difficulty=difficulty,
                current_score=current_score,
            ),
        ]
    return [
        _make_drill(
            drill_id="articulation-contrast-pairs",
            title="Articulation contrast pairs",
            focus_dimension=dimension,
            rationale="Articulation variety is currently under-developed.",
            instructions="Alternate legato and staccato versions of the same bar for 6 repetitions.",
            difficulty=difficulty,
            current_score=current_score,
        ),
        _make_drill(
            drill_id="articulation-grouping",
            title="Phrase grouping drill",
            focus_dimension=dimension,
            rationale="Clear note-grouping improves phrasing and interpretive consistency.",
            instructions="Group notes 2+2 then 3+1 while keeping pulse and pitch locked.",
            difficulty=difficulty,
            current_score=current_score,
        ),
    ]


def _recommend_drills(profile: MusicSkillProfile) -> list[dict[str, object]]:
    metrics = _profile_metrics(profile)
    ranked = sorted(metrics.items(), key=lambda item: item[1])
    difficulty = _difficulty_for_profile(profile)
    weakest, second_weakest = ranked[0][0], ranked[1][0]

    drills: list[dict[str, object]] = []
    drills.extend(_drills_for_dimension(weakest, difficulty=difficulty, current_score=metrics[weakest])[:2])
    drills.extend(_drills_for_dimension(second_weakest, difficulty=difficulty, current_score=metrics[second_weakest])[:1])
    return drills


def _make_tutor_prompt(profile: MusicSkillProfile, drills: list[dict[str, object]]) -> str:
    metrics = _profile_metrics(profile)
    weakest = profile.weakest_dimension
    weakest_score = _round3(metrics.get(weakest, 0.0))
    overall = _round3(_overall_score(metrics))
    drill_titles = ", ".join(str(item["title"]) for item in drills[:2])
    return (
        "Coach this student in concise, bar-specific steps. "
        f"Weakest dimension: {weakest} ({weakest_score}). Overall rolling score: {overall}. "
        f"Prioritize drills: {drill_titles}. Give two concrete technique cues and one short theory note."
    )


def _profile_payload(profile: MusicSkillProfile) -> dict[str, object]:
    metrics = _profile_metrics(profile)
    return {
        "weakest_dimension": profile.weakest_dimension,
        "consistency_score": _round3(profile.consistency_score),
        "practice_frequency": _round3(profile.practice_frequency),
        "last_improvement_trend": _round3(profile.last_improvement_trend),
        "sample_count": int(profile.sample_count),
        "rolling_metrics": {
            "pitchAccuracy": _round3(metrics["pitch"]),
            "rhythmAccuracy": _round3(metrics["rhythm"]),
            "tempoStability": _round3(metrics["tempo"]),
            "dynamicRange": _round3(metrics["dynamics"]),
            "articulationVariance": _round3(metrics["articulation"]),
        },
    }


async def update_user_skill_profile(
    db: AsyncSession,
    *,
    user_id: str,
    instrument_profile: str,
    performance_feedback: dict[str, float],
) -> tuple[dict[str, object], list[dict[str, object]], str]:
    """Update deterministic adaptive profile and return recommendation payload."""
    query = await db.execute(select(MusicSkillProfile).where(MusicSkillProfile.user_id == user_id))
    profile = query.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    metrics = _extract_metrics(performance_feedback)
    current_overall = _overall_score(metrics)

    if profile is None:
        profile = MusicSkillProfile(
            user_id=user_id,
            instrument_profile=(instrument_profile or "AUTO").upper(),
            sample_count=0,
        )
        previous_overall = current_overall
        instant_frequency = 0.25
    else:
        previous_overall = _clamp01(_as_float(profile.overall_score))
        if profile.last_practiced_at is None:
            instant_frequency = 0.25
        else:
            elapsed_seconds = max(60.0, (now - profile.last_practiced_at).total_seconds())
            sessions_per_day = min(2.0, 86400.0 / elapsed_seconds)
            instant_frequency = _clamp01(sessions_per_day / 2.0)

    alpha = 0.28
    if profile.sample_count <= 0:
        profile.pitch_score = metrics["pitch"]
        profile.rhythm_score = metrics["rhythm"]
        profile.tempo_score = metrics["tempo"]
        profile.dynamics_score = metrics["dynamics"]
        profile.articulation_score = metrics["articulation"]
        profile.consistency_jitter = 0.0
    else:
        profile.pitch_score = _clamp01((alpha * metrics["pitch"]) + ((1 - alpha) * _as_float(profile.pitch_score)))
        profile.rhythm_score = _clamp01((alpha * metrics["rhythm"]) + ((1 - alpha) * _as_float(profile.rhythm_score)))
        profile.tempo_score = _clamp01((alpha * metrics["tempo"]) + ((1 - alpha) * _as_float(profile.tempo_score)))
        profile.dynamics_score = _clamp01(
            (alpha * metrics["dynamics"]) + ((1 - alpha) * _as_float(profile.dynamics_score))
        )
        profile.articulation_score = _clamp01(
            (alpha * metrics["articulation"]) + ((1 - alpha) * _as_float(profile.articulation_score))
        )
        delta = abs(current_overall - previous_overall)
        profile.consistency_jitter = (0.7 * _as_float(profile.consistency_jitter)) + (0.3 * delta)

    profile.sample_count = int(profile.sample_count) + 1
    profile.instrument_profile = (instrument_profile or "AUTO").upper()
    profile.last_improvement_trend = _clamp_signed(current_overall - previous_overall)
    profile.consistency_score = _clamp01(1.0 - (_as_float(profile.consistency_jitter) / 0.35))
    profile.practice_frequency = _clamp01((0.35 * instant_frequency) + (0.65 * _as_float(profile.practice_frequency)))
    profile.overall_score = _overall_score(_profile_metrics(profile))
    profile.last_practiced_at = now

    ranked_dimensions = sorted(_profile_metrics(profile).items(), key=lambda item: item[1])
    profile.weakest_dimension = ranked_dimensions[0][0]

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    drills = _recommend_drills(profile)
    tutor_prompt = _make_tutor_prompt(profile, drills)
    return _profile_payload(profile), drills, tutor_prompt
