"""Tool registry assembly."""

from __future__ import annotations

from .drill import build_drill_generation_tool
from .grade import build_grade_response_tool
from .parse import build_parse_tool
from .registry import ToolRegistry
from .runtime import ToolExecutionError, execute_tool_call


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            build_parse_tool(),
            build_grade_response_tool(),
            build_drill_generation_tool(),
        ]
    )


__all__ = [
    "ToolExecutionError",
    "build_default_tool_registry",
    "execute_tool_call",
]
