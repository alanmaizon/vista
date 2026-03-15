from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domains.music.context import compose_live_context_packet, select_relevant_library_items
from app.domains.music.models import MusicLibraryItem, MusicPerformanceAttempt, MusicSkillProfile


def _library_item(
    *,
    title: str,
    tags: list[str],
    objective: str,
    curated: bool = True,
    instrument: str = "PIANO",
) -> MusicLibraryItem:
    item = MusicLibraryItem(
        id=uuid.uuid4(),
        owner_user_id="music-user",
        is_curated=curated,
        content_type="EXERCISE",
        title=title,
        description="Test item",
        instrument=instrument,
        difficulty="BEGINNER",
        technique_tags=tags,
        learning_objective=objective,
        source_format="NOTE_LINE",
        source_text="C4/q D4/q",
        metadata_json={},
    )
    item.created_at = datetime.now(timezone.utc)
    return item


def _attempt(
    *,
    summary: str,
    accuracy: float,
    match: bool,
    needs_replay: bool,
    measure_index: int = 1,
) -> MusicPerformanceAttempt:
    attempt = MusicPerformanceAttempt(
        id=uuid.uuid4(),
        user_id="music-user",
        score_id=uuid.uuid4(),
        measure_index=measure_index,
        instrument_profile="PIANO",
        accuracy=accuracy,
        match=match,
        needs_replay=needs_replay,
        summary=summary,
        performance_feedback={"pitchAccuracy": accuracy},
    )
    attempt.created_at = datetime.now(timezone.utc)
    return attempt


def test_select_relevant_library_items_prioritizes_weak_dimension_tags() -> None:
    profile = MusicSkillProfile(
        user_id="music-user",
        instrument_profile="PIANO",
        weakest_dimension="rhythm",
        sample_count=6,
    )
    rhythm = _library_item(
        title="Rhythm Subdivision Drill",
        tags=["rhythm", "timing"],
        objective="Stabilize groove and subdivision.",
    )
    intonation = _library_item(
        title="Pitch Ladder",
        tags=["intonation"],
        objective="Improve intonation stability.",
    )
    neutral = _library_item(
        title="Warmup",
        tags=["warmup"],
        objective="General warmup.",
    )
    selected = select_relevant_library_items(
        [intonation, neutral, rhythm],
        profile=profile,
        goal="Help me tighten rhythm and timing",
        limit=2,
    )

    assert len(selected) == 2
    assert selected[0].title == "Rhythm Subdivision Drill"


def test_compose_live_context_packet_includes_profile_attempts_and_library() -> None:
    profile = MusicSkillProfile(
        user_id="music-user",
        instrument_profile="PIANO",
        weakest_dimension="rhythm",
        consistency_score=0.64,
        practice_frequency=0.52,
        overall_score=0.59,
        sample_count=7,
    )
    attempts = [
        _attempt(
            summary="Replay requested for bar 2 timing.",
            accuracy=0.58,
            match=False,
            needs_replay=True,
            measure_index=2,
        ),
        _attempt(
            summary="Bar 1 was stable.",
            accuracy=0.86,
            match=True,
            needs_replay=False,
            measure_index=1,
        ),
    ]
    items = [
        _library_item(
            title="Rhythm Repair",
            tags=["rhythm", "timing"],
            objective="Repair bar-level timing drift.",
        )
    ]

    packet = compose_live_context_packet(
        skill="GUIDED_LESSON",
        goal="Learn this phrase bar by bar",
        profile=profile,
        attempts=attempts,
        library_items=items,
        max_chars=2400,
    )

    assert "SESSION_SKILL: GUIDED_LESSON" in packet
    assert "PROFILE:" in packet
    assert "RECENT_ATTEMPTS:" in packet
    assert "RELEVANT_LIBRARY_ITEMS:" in packet
    assert "Rhythm Repair" in packet
    assert "CONTEXT_POLICY:" in packet

