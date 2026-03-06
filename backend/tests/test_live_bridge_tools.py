from __future__ import annotations

from app.live.bridge import _parse_text_tool_call


def test_parse_text_tool_call_extracts_name_args_and_call_id() -> None:
    event = _parse_text_tool_call(
        'TOOL_CALL: {"id":"tool-1","name":"lesson_step","args":{"score_id":"abc"}}'
    )
    assert event is not None
    assert event["type"] == "server.tool_call"
    assert event["call_id"] == "tool-1"
    assert event["name"] == "lesson_step"
    assert event["args"] == {"score_id": "abc"}


def test_parse_text_tool_call_returns_none_for_invalid_json() -> None:
    assert _parse_text_tool_call("TOOL_CALL: {not-json}") is None

