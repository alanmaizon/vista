from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class LiveAgentContext:
    """Minimal session context for the reset live backend."""

    mode: str = "music_tutor"
    instrument: str | None = None
    piece: str | None = None
    goal: str | None = None


def context_from_init(message: dict[str, Any]) -> LiveAgentContext:
    return LiveAgentContext(
        mode=_clean_text(message.get("mode")) or "music_tutor",
        instrument=_clean_text(message.get("instrument")),
        piece=_clean_text(message.get("piece")),
        goal=_clean_text(message.get("goal")),
    )


def build_system_prompt(context: LiveAgentContext) -> str:
    context_lines = []
    if context.instrument:
        context_lines.append(f"Instrument: {context.instrument}.")
    if context.piece:
        context_lines.append(f"Piece: {context.piece}.")
    if context.goal:
        context_lines.append(f"User goal: {context.goal}.")

    context_block = " ".join(context_lines).strip()

    return " ".join(
        part
        for part in [
            "You are Eurydice Live, a real-time music tutor in a voice-and-camera session.",
            "Keep responses short and natural: usually one or two sentences.",
            "Ask only one follow-up question at a time.",
            "If the user shows music to the camera, describe only what is clearly visible and never invent notes.",
            "If room noise or bystander speech seems unrelated to music practice, do not treat it as the user's request.",
            "Instead, briefly ask the user to restate the musical question or show the score again.",
            "If the user interrupts you, adapt immediately and continue naturally.",
            "Prefer practical coaching over theory lectures.",
            context_block,
        ]
        if part
    )


def build_opening_user_prompt(context: LiveAgentContext) -> str:
    known_context = []
    if context.instrument:
        known_context.append(f"instrument={context.instrument}")
    if context.piece:
        known_context.append(f"piece={context.piece}")
    if context.goal:
        known_context.append(f"goal={context.goal}")

    if known_context:
        joined = ", ".join(known_context)
        return (
            "Start the session with a brief spoken greeting. "
            f"Acknowledge this context: {joined}. "
            "Then ask one short next-step question."
        )

    return (
        "Start the session with a brief spoken greeting and ask what piece, "
        "technique, or music problem the user wants help with."
    )
