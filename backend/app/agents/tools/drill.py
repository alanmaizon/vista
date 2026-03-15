"""Placeholder drill generation tool."""

from __future__ import annotations

from .registry import ToolSpec


def build_drill_generation_tool() -> ToolSpec:
    return ToolSpec(
        name="generate_drill",
        description="Create a short follow-up drill from a recent learner mistake.",
        notes="Placeholder: eventually emit a targeted morphology or translation micro-exercise.",
        input_schema={
            "type": "object",
            "properties": {
                "mistake_summary": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["mistake_summary"],
        },
    )

