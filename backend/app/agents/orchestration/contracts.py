"""Shared data contracts for live turn orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ...schemas import TutorMode


@dataclass(frozen=True)
class LiveTurnInput:
    turn_id: str
    reason: str
    learner_text: str = ""
    audio_chunk_count: int = 0
    image_frame_count: int = 0


@dataclass(frozen=True)
class TurnPolicyContext:
    mode: TutorMode
    target_text: str | None
    preferred_response_language: str
    turn_input: LiveTurnInput


@dataclass(frozen=True)
class TurnPlan:
    engine: Literal["google-adk", "heuristic-fallback"]
    stage: Literal["tool_preflight", "direct_generation"]
    rationale: str
    preflight_tool_name: str | None = None
    preflight_tool_arguments: dict[str, Any] = field(default_factory=dict)
