"""Tutoring mode definitions."""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import ModeSummary, TutorMode


@dataclass(frozen=True)
class ModeDefinition:
    label: str
    goal: str
    first_turn: str


MODE_DEFINITIONS: dict[TutorMode, ModeDefinition] = {
    TutorMode.guided_reading: ModeDefinition(
        label="Guided Reading",
        goal="Help the learner read a short passage aloud and stay oriented in the syntax.",
        first_turn="Invite the learner to read one clause aloud, then focus on the first unknown form.",
    ),
    TutorMode.morphology_coach: ModeDefinition(
        label="Morphology Coach",
        goal="Coach endings, stems, and inflection choices without jumping straight to full translation.",
        first_turn="Ask which word is blocking the learner, then narrow to case, number, tense, or mood.",
    ),
    TutorMode.translation_support: ModeDefinition(
        label="Translation Support",
        goal="Guide the learner toward a defensible translation with hints rather than full answers.",
        first_turn="Have the learner propose a rough translation and repair one phrase at a time.",
    ),
    TutorMode.oral_reading: ModeDefinition(
        label="Oral Reading",
        goal="Support pronunciation, pacing, and chunking for spoken Ancient Greek practice.",
        first_turn="Set a short reading target and listen for pacing or pronunciation breakdowns.",
    ),
}


def get_mode_definition(mode: TutorMode) -> ModeDefinition:
    return MODE_DEFINITIONS[mode]


def list_mode_summaries() -> list[ModeSummary]:
    return [
        ModeSummary(
            value=mode,
            label=definition.label,
            goal=definition.goal,
            first_turn=definition.first_turn,
        )
        for mode, definition in MODE_DEFINITIONS.items()
    ]

