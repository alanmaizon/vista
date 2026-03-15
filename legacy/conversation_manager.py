"""
Manages the state and history of a single conversation session.

This module is the single source of truth for:
- Turn history (user, assistant, tool calls, tool results).
- Building context for the language model.
- Persisting relevant state for session resumption.
- Compacting older turns to manage context window size.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Literal


# A simplified event model for now.
# This can be expanded with Pydantic models later.
ConversationEvent = dict[str, Any]


@dataclass
class ConversationManager:
    """Orchestrates the lifecycle of a live conversation."""

    session_id: uuid.UUID
    user_id: str
    events: Deque[ConversationEvent] = field(default_factory=lambda: deque(maxlen=100))
    _turn_counter: int = 0

    def _create_event(
        self,
        event_type: Literal["user", "assistant", "tool_call", "tool_result", "system"],
        content: dict[str, Any],
    ) -> ConversationEvent:
        """Factory for creating normalized conversation events."""
        self._turn_counter += 1
        return {
            "event_id": f"{self.session_id}-{self._turn_counter}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **content,
        }

    def add_user_turn(self, text: str) -> None:
        """Append a user text message to the history."""
        event = self._create_event("user", {"text": text})
        self.events.append(event)

    def add_assistant_turn(self, text: str) -> None:
        """Append an assistant text message to the history."""
        event = self._create_event("assistant", {"text": text})
        self.events.append(event)

    def add_tool_call(self, name: str, args: dict[str, Any], call_id: str | None = None) -> None:
        """Append a model-invoked tool call to the history."""
        event = self._create_event("tool_call", {"name": name, "args": args, "call_id": call_id})
        self.events.append(event)

    def add_tool_result(
        self,
        name: str,
        result: dict[str, Any] | None,
        error: str | None = None,
        call_id: str | None = None,
    ) -> None:
        """Append a tool result to the history, linking it to a call if possible."""
        event = self._create_event(
            "tool_result",
            {"name": name, "result": result, "error": error, "call_id": call_id},
        )
        self.events.append(event)

    def get_full_history(self) -> list[ConversationEvent]:
        """Return the full, ordered list of events."""
        return list(self.events)