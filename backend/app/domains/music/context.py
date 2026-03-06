"""Live context retrieval for Eurydice music sessions.

This module builds a compact context packet to enrich live model sessions with
deterministic backend facts: user skill profile, recent attempts, and relevant
library items.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MusicLibraryItem, MusicPerformanceAttempt, MusicSkillProfile

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")

_DIMENSION_TAGS: dict[str, set[str]] = {
    "pitch": {"intonation", "intervals", "ear-training"},
    "rhythm": {"rhythm", "subdivision", "timing", "groove"},
    "tempo": {"tempo", "timing", "metronome"},
    "dynamics": {"dynamics", "expression", "control"},
    "articulation": {"articulation", "phrasing", "staccato", "legato"},
}


def _normalize_tag(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _tokenize(value: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(value or "")}


def _safe_timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    try:
        return float(value.timestamp())
    except Exception:
        return 0.0


def _fmt_ratio(value: float | None) -> str:
    numeric = float(value or 0.0)
    numeric = max(0.0, min(1.0, numeric))
    return f"{round(numeric * 100)}%"


def _profile_target_tags(profile: MusicSkillProfile | None) -> set[str]:
    if profile is None:
        return {"timing"}
    weakest = (profile.weakest_dimension or "").strip().lower()
    return _DIMENSION_TAGS.get(weakest, {"timing"})


def select_relevant_library_items(
    items: Iterable[MusicLibraryItem],
    *,
    profile: MusicSkillProfile | None,
    goal: str | None,
    limit: int,
) -> list[MusicLibraryItem]:
    """Pick the most relevant library items for a live session context packet."""
    safe_limit = max(1, min(12, int(limit)))
    target_tags = _profile_target_tags(profile)
    goal_tokens = _tokenize(goal or "")
    preferred_instrument = ""
    if profile is not None:
        instrument = (profile.instrument_profile or "").strip().upper()
        if instrument and instrument != "AUTO":
            preferred_instrument = instrument

    scored: list[tuple[tuple[int, int, int, int, float], MusicLibraryItem]] = []
    for item in items:
        tags = {_normalize_tag(tag) for tag in (item.technique_tags or []) if isinstance(tag, str)}
        text_tokens = _tokenize(
            " ".join(
                [
                    item.title or "",
                    item.description or "",
                    item.learning_objective or "",
                ]
            )
        )
        target_match_count = len(tags.intersection(target_tags))
        goal_match_count = len(goal_tokens.intersection(tags.union(text_tokens)))
        instrument_match = 1 if preferred_instrument and item.instrument.upper() == preferred_instrument else 0
        curated_bonus = 1 if bool(item.is_curated) else 0
        recency = _safe_timestamp(item.created_at)
        score_key = (
            target_match_count,
            goal_match_count,
            instrument_match,
            curated_bonus,
            recency,
        )
        scored.append((score_key, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in scored[:safe_limit]]


def compose_live_context_packet(
    *,
    skill: str,
    goal: str | None,
    profile: MusicSkillProfile | None,
    attempts: list[MusicPerformanceAttempt],
    library_items: list[MusicLibraryItem],
    max_chars: int,
) -> str:
    """Compose a deterministic, compact context packet for live prompts."""
    safe_chars = max(512, int(max_chars))
    lines: list[str] = []
    lines.append(f"SESSION_SKILL: {skill}")
    if goal:
        lines.append(f"GOAL: {goal.strip()}")

    if profile is not None:
        lines.append(
            "PROFILE: "
            f"weakest_dimension={profile.weakest_dimension or 'pitch'}; "
            f"instrument={profile.instrument_profile or 'AUTO'}; "
            f"overall={_fmt_ratio(profile.overall_score)}; "
            f"consistency={_fmt_ratio(profile.consistency_score)}; "
            f"practice_frequency={_fmt_ratio(profile.practice_frequency)}; "
            f"samples={int(profile.sample_count or 0)}"
        )

    if attempts:
        lines.append("RECENT_ATTEMPTS:")
        for attempt in attempts:
            summary = (attempt.summary or "").strip()
            if len(summary) > 96:
                summary = summary[:93].rstrip() + "..."
            lines.append(
                "- "
                f"measure={attempt.measure_index or 'n/a'}; "
                f"accuracy={_fmt_ratio(attempt.accuracy)}; "
                f"match={'yes' if attempt.match else 'no'}; "
                f"replay={'yes' if attempt.needs_replay else 'no'}; "
                f"summary={summary or 'n/a'}"
            )

    if library_items:
        lines.append("RELEVANT_LIBRARY_ITEMS:")
        for item in library_items:
            tags = ",".join(str(tag) for tag in (item.technique_tags or [])[:4]) or "none"
            objective = (item.learning_objective or "").strip()
            if len(objective) > 80:
                objective = objective[:77].rstrip() + "..."
            lines.append(
                "- "
                f"title={item.title}; "
                f"type={item.content_type}; "
                f"difficulty={item.difficulty}; "
                f"instrument={item.instrument}; "
                f"tags={tags}; "
                f"objective={objective or 'n/a'}"
            )

    lines.append(
        "CONTEXT_POLICY: Treat this as supporting context only. Prioritize live audio/video evidence. "
        "If evidence is unclear or conflicts, request replay or reframing before concluding."
    )

    packet = "\n".join(lines).strip()
    if len(packet) <= safe_chars:
        return packet
    truncated = packet[: max(0, safe_chars - 13)].rstrip()
    return f"{truncated}\n[truncated]"


async def build_music_live_context(
    db: AsyncSession,
    *,
    user_id: str,
    skill: str,
    goal: str | None,
    attempt_limit: int,
    library_limit: int,
    max_chars: int,
) -> str:
    """Retrieve and compose a live context packet from persisted music data."""
    safe_attempt_limit = max(1, min(12, int(attempt_limit)))
    safe_library_limit = max(1, min(12, int(library_limit)))

    profile_result = await db.execute(select(MusicSkillProfile).where(MusicSkillProfile.user_id == user_id))
    profile = profile_result.scalar_one_or_none()

    attempts_result = await db.execute(
        select(MusicPerformanceAttempt)
        .where(MusicPerformanceAttempt.user_id == user_id)
        .order_by(MusicPerformanceAttempt.created_at.desc())
    )
    attempts = list(attempts_result.scalars().all())[:safe_attempt_limit]

    items_result = await db.execute(select(MusicLibraryItem))
    visible_items = [
        item
        for item in items_result.scalars().all()
        if bool(item.is_curated) or (item.owner_user_id or "") == user_id
    ]
    selected_items = select_relevant_library_items(
        visible_items,
        profile=profile,
        goal=goal,
        limit=safe_library_limit,
    )
    return compose_live_context_packet(
        skill=skill,
        goal=goal,
        profile=profile,
        attempts=attempts,
        library_items=selected_items,
        max_chars=max_chars,
    )

