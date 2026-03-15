"""Placeholder parsing tool."""

from __future__ import annotations

from .registry import ToolSpec


def build_parse_tool() -> ToolSpec:
    return ToolSpec(
        name="parse_passage",
        description="Break a learner-selected Greek word or clause into morphology and syntax hints.",
        notes="Placeholder: later return lemma, inflection, gloss, and dependency cues.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "focus_word": {"type": "string"},
            },
            "required": ["text"],
        },
    )

