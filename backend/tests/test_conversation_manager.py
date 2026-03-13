from __future__ import annotations

import uuid

import pytest

from app.conversation_manager import ConversationManager


def _manager() -> ConversationManager:
    return ConversationManager(session_id=uuid.uuid4(), user_id="test-user")


def test_text_turns_require_non_empty_text() -> None:
    manager = _manager()

    with pytest.raises(ValueError):
        manager.add_user_turn("   ")
    with pytest.raises(ValueError):
        manager.add_assistant_turn("")


def test_register_tool_call_dedupes_call_ids() -> None:
    manager = _manager()

    call_id, is_new = manager.register_tool_call("lesson_action", {"step": "prepare"}, call_id="call-1")
    assert call_id == "call-1"
    assert is_new is True
    assert len(manager.get_full_history()) == 1

    duplicate_call_id, duplicate_is_new = manager.register_tool_call(
        "lesson_action",
        {"step": "prepare"},
        call_id="call-1",
    )
    assert duplicate_call_id == "call-1"
    assert duplicate_is_new is False
    assert len(manager.get_full_history()) == 1


def test_register_tool_result_rejects_duplicate_completed_call() -> None:
    manager = _manager()

    call_id, is_new = manager.register_tool_call("lesson_step", {"score_id": "s-1"}, call_id="call-2")
    assert is_new is True
    assert call_id == "call-2"

    first_result = manager.register_tool_result("lesson_step", {"ok": True}, call_id="call-2")
    duplicate_result = manager.register_tool_result("lesson_step", {"ok": True}, call_id="call-2")

    assert first_result is True
    assert duplicate_result is False
    assert len(manager.get_full_history()) == 2
