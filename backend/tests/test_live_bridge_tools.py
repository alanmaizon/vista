from __future__ import annotations

from app.live.bridge import _DirectGeminiLiveBridge, _LiveEventSequencer, _parse_text_tool_call


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


def test_live_event_sequencer_reuses_turn_id_until_completion() -> None:
    sequencer = _LiveEventSequencer()

    partial = sequencer.new_transcript_event(role="assistant", text="Hello", partial=True)
    final_text = sequencer.new_text_event("Hello there", turn_complete=True)

    assert partial["turn_id"] == final_text["turn_id"]
    assert partial["chunk_index"] == 0
    assert final_text["chunk_index"] == 1

    sequencer.complete_assistant_turn()
    next_turn = sequencer.new_text_event("Next turn", turn_complete=True)
    assert next_turn["turn_id"] != final_text["turn_id"]


def test_direct_live_bridge_setup_disables_server_activity_detection() -> None:
    bridge = _DirectGeminiLiveBridge(
        model_id="gemini-live-2.5-flash-native-audio",
        location="us-central1",
        fallback_location="us-central1",
        project_id="test-project",
        system_prompt="Be brief.",
        skill="MUSIC_LIVE_TUTOR",
        goal=None,
    )

    setup = bridge._setup_message("us-central1")
    aad = setup["setup"]["realtime_input_config"]["automatic_activity_detection"]
    assert aad["disabled"] is True
