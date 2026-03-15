"""Placeholder grading tool."""

from __future__ import annotations

from .registry import ToolSpec


def build_grade_response_tool() -> ToolSpec:
    return ToolSpec(
        name="grade_attempt",
        description="Evaluate how close the learner's spoken or typed answer is to the target reading or translation.",
        notes="Placeholder: later combine deterministic checks with model-backed qualitative feedback.",
        input_schema={
            "type": "object",
            "properties": {
                "learner_answer": {"type": "string"},
                "reference_answer": {"type": "string"},
            },
            "required": ["learner_answer"],
        },
    )

