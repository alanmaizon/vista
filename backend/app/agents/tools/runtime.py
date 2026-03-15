"""Tool execution runtime for deterministic scaffold tools."""

from __future__ import annotations

from typing import Any, Callable

from .drill import execute_drill_tool
from .grade import execute_grade_tool
from .parse import execute_parse_tool
from .reference import execute_resolve_reference_tool


class ToolExecutionError(RuntimeError):
    """Raised when a tool call is invalid or execution fails."""


ToolExecutor = Callable[[dict[str, Any]], dict[str, Any]]


_EXECUTORS: dict[str, ToolExecutor] = {
    "resolve_reference": execute_resolve_reference_tool,
    "parse_passage": execute_parse_tool,
    "grade_attempt": execute_grade_tool,
    "generate_drill": execute_drill_tool,
}


def execute_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    executor = _EXECUTORS.get(tool_name)
    if executor is None:
        raise ToolExecutionError(f"Unknown tool '{tool_name}'")

    try:
        return executor(arguments)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise ToolExecutionError(f"Tool '{tool_name}' failed unexpectedly: {exc}") from exc
