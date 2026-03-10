"""
Generic tool registry and execution framework.

This provides a decoupled way to define, register, and execute
deterministic tools that can be called by the language model or the client.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from collections import deque
from typing import Any, Callable, Coroutine, Deque

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


class ToolError(Exception):
    """Base exception for tool execution errors."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ToolSpec:
    """A specification for a tool that can be executed."""

    name: str
    description: str
    args_schema: type[BaseModel]
    # The executor takes (db, user_id, args) and returns a dict
    executor: Callable[[AsyncSession, str, BaseModel], Coroutine[Any, Any, dict[str, Any]]]
    is_cacheable: bool = False


class ToolRegistry:
    """A registry for discoverable and executable tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_keys: Deque[str] = deque(maxlen=100)

    def register(self, tool: ToolSpec) -> None:
        """Register a new tool."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get_tool_prompt(self) -> str:
        """Generate a prompt fragment describing all registered tools."""
        if not self._tools:
            return ""

        tool_descriptions = "\n".join(f'- `{spec.name}`: {spec.description}' for spec in self._tools.values())

        return (
            "If you need deterministic score/lesson data, request a tool call by emitting exactly one line:\n"
            'TOOL_CALL: {"name":"<tool_name>","args":{...}}\n'
            "Supported tool names and their descriptions:\n"
            f"{tool_descriptions}\n"
            "Do not include extra prose in a TOOL_CALL line."
        )

    def _get_cache_key(self, tool_name: str, args: dict[str, Any]) -> str:
        """Create a stable hash key for caching tool results."""
        # Create a stable string from args by sorting keys
        stable_args = json.dumps(args, sort_keys=True, separators=(",", ":"))
        key_string = f"{tool_name}:{stable_args}"
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    async def run_tool(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        tool_name: str,
        args: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Find and execute a tool by name."""
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ToolError("tool name is required.")

        normalized_name = tool_name.strip().lower()
        spec = self._tools.get(normalized_name)
        if spec is None:
            available = ", ".join(self._tools.keys())
            raise ToolError(f"Unsupported tool '{normalized_name}'. Supported tools: {available}.")

        try:
            validated_args = spec.args_schema.model_validate(args or {})
        except ValidationError as exc:
            # Taking the first error for simplicity
            error_msg = exc.errors()[0].get("msg", "Invalid tool arguments.")
            raise ToolError(error_msg) from exc

        if not spec.is_cacheable:
            return await spec.executor(db, user_id, validated_args)

        # Handle caching for cacheable tools
        cache_key = self._get_cache_key(normalized_name, validated_args.model_dump(mode="json"))
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await spec.executor(db, user_id, validated_args)

        if len(self._cache) >= (self._cache_keys.maxlen or 100):
            oldest_key = self._cache_keys.popleft()
            if oldest_key in self._cache:
                del self._cache[oldest_key]

        self._cache[cache_key] = result
        self._cache_keys.append(cache_key)
        return result


# Global registry instance
tool_registry = ToolRegistry()