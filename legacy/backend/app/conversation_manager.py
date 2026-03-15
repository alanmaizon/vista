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
from collections import OrderedDict
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
    events: Deque[ConversationEvent] = field(default_factory=lambda: deque(maxlen=200))
    _turn_counter: int = 0
    _pending_tool_calls: OrderedDict[str, str] = field(default_factory=OrderedDict)
    _completed_tool_calls: OrderedDict[str, str] = field(default_factory=OrderedDict)
    _max_tracked_tool_calls: int = 200

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

    @staticmethod
    def _validate_text(text: str, *, field_name: str = "text") -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError(f"{field_name} must be non-empty text.")
        return cleaned

    @staticmethod
    def _merge_text(existing: str, incoming: str) -> str:
        current = (existing or "").strip()
        update = (incoming or "").strip()
        if not current:
            return update
        if not update:
            return current
        if update == current:
            return current
        if update.startswith(current):
            return update
        if current.startswith(update):
            return current
        omit_space = update[:1] in {",", ".", ";", ":", "!", "?", ")"} or current[-1:] in {"(", "/", '"', "'"}
        merged = f"{current}{'' if omit_space else ' '}{update}"
        return merged.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")

    @staticmethod
    def _validate_tool_name(name: str) -> str:
        cleaned = (name or "").strip().lower()
        if not cleaned:
            raise ValueError("tool name must be non-empty.")
        return cleaned

    def _new_call_id(self) -> str:
        return f"tool-{uuid.uuid4()}"

    def _remember_completed_call(self, call_id: str, event_id: str) -> None:
        self._completed_tool_calls[call_id] = event_id
        self._completed_tool_calls.move_to_end(call_id)
        while len(self._completed_tool_calls) > self._max_tracked_tool_calls:
            self._completed_tool_calls.popitem(last=False)

    def register_tool_call(
        self,
        name: str,
        args: dict[str, Any],
        call_id: str | None = None,
    ) -> tuple[str, bool]:
        """Record a tool call and dedupe repeated call identifiers.

        Returns ``(resolved_call_id, is_new)``.
        """
        tool_name = self._validate_tool_name(name)
        if not isinstance(args, dict):
            raise ValueError("tool args must be an object.")
        resolved_call_id = (call_id or "").strip() or self._new_call_id()
        if resolved_call_id in self._pending_tool_calls or resolved_call_id in self._completed_tool_calls:
            return resolved_call_id, False

        event = self._create_event(
            "tool_call",
            {"name": tool_name, "args": args, "call_id": resolved_call_id},
        )
        self.events.append(event)
        self._pending_tool_calls[resolved_call_id] = event["event_id"]
        self._pending_tool_calls.move_to_end(resolved_call_id)
        while len(self._pending_tool_calls) > self._max_tracked_tool_calls:
            self._pending_tool_calls.popitem(last=False)
        return resolved_call_id, True

    def register_tool_result(
        self,
        name: str,
        result: dict[str, Any] | None,
        *,
        error: str | None = None,
        call_id: str | None = None,
    ) -> bool:
        """Record a tool result, rejecting duplicate settled call ids."""
        tool_name = self._validate_tool_name(name)
        resolved_call_id = (call_id or "").strip()
        if resolved_call_id and resolved_call_id in self._completed_tool_calls:
            return False
        if resolved_call_id:
            self._pending_tool_calls.pop(resolved_call_id, None)
        event = self._create_event(
            "tool_result",
            {
                "name": tool_name,
                "result": result,
                "error": (error or "").strip() or None,
                "call_id": resolved_call_id or None,
            },
        )
        self.events.append(event)
        if resolved_call_id:
            self._remember_completed_call(resolved_call_id, event["event_id"])
        return True

    def add_user_turn(self, text: str) -> None:
        """Append a user text message to the history."""
        event = self._create_event("user", {"text": self._validate_text(text)})
        self.events.append(event)

    def add_assistant_turn(self, text: str, *, turn_id: str | None = None) -> None:
        """Append an assistant text message to the history."""
        cleaned = self._validate_text(text)
        normalized_turn_id = (turn_id or "").strip() or None
        if normalized_turn_id:
            for event in reversed(self.events):
                if event.get("type") == "assistant" and event.get("turn_id") == normalized_turn_id:
                    event["text"] = self._merge_text(str(event.get("text", "")), cleaned)
                    return
        payload: dict[str, Any] = {"text": cleaned}
        if normalized_turn_id:
            payload["turn_id"] = normalized_turn_id
        event = self._create_event("assistant", payload)
        self.events.append(event)

    def add_tool_call(self, name: str, args: dict[str, Any], call_id: str | None = None) -> None:
        """Append a model-invoked tool call to the history."""
        self.register_tool_call(name=name, args=args, call_id=call_id)

    def add_tool_result(
        self,
        name: str,
        result: dict[str, Any] | None,
        error: str | None = None,
        call_id: str | None = None,
    ) -> None:
        """Append a tool result to the history, linking it to a call if possible."""
        self.register_tool_result(name=name, result=result, error=error, call_id=call_id)

    def get_full_history(self) -> list[ConversationEvent]:
        """Return the full, ordered list of events."""
        return list(self.events)
