"""Shared tool registry objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ...schemas import ToolDefinition


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    notes: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    status: str = "placeholder"


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolSpec]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def list_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                notes=tool.notes,
                input_schema=tool.input_schema,
                status=tool.status,
            )
            for tool in self._tools.values()
        ]

