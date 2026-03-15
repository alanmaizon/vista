from __future__ import annotations

from app.domains.music.lesson_intents import LessonIntentRouter, LessonRoutingInput


def _route(text: str, *, phase: str, metadata: dict | None = None):
    router = LessonIntentRouter()
    return router.route_user_input(
        LessonRoutingInput(
            latest_user_transcript=text,
            current_phase=phase,
            recent_conversation_context=(),
            deterministic_tool_outputs=None,
            music_phrase_events=(),
            session_metadata=metadata or {},
        )
    )


def test_router_classifies_feedback_request_and_phrase_play() -> None:
    feedback = _route("Was that right?", phase="feedback")
    phrase = _route("Let me try", phase="exercise_selection")

    assert feedback.intent == "ASK_FEEDBACK"
    assert feedback.recommended_transition == "listening"
    assert phrase.intent == "PLAYED_PHRASE"
    assert phrase.recommended_transition == "listening"


def test_router_handles_ambiguous_followups_phase_aware() -> None:
    repeat = _route("one more time", phase="feedback")
    explain = _route("I don't get it", phase="next_step")
    next_step = _route("what now?", phase="feedback")

    assert repeat.intent == "REPEAT_REQUEST"
    assert repeat.recommended_transition == "listening"
    assert explain.intent == "CONFUSED_FOLLOWUP"
    assert explain.recommended_transition == "feedback"
    assert next_step.intent == "READY_FOR_NEXT_STEP"
    assert next_step.recommended_transition == "next_step"


def test_router_supports_stop_and_silence_timeout() -> None:
    stop = _route("stop for now", phase="exercise_selection")
    silence = _route(
        "",
        phase="listening",
        metadata={"silence_timeout": True, "timeout_seconds": 12},
    )

    assert stop.intent == "STOP_REQUEST"
    assert stop.recommended_transition == "session_complete"
    assert silence.intent == "SILENCE_TIMEOUT"
    assert silence.recommended_transition == "next_step"
    assert silence.entities["timeout_seconds"] == 12


def test_router_routes_tool_and_music_events() -> None:
    router = LessonIntentRouter()
    tool_event = router.route_tool_output(
        tool_name="transcribe",
        ok=True,
        result={"summary": "deterministic summary", "confidence": 0.8},
        error=None,
        current_phase="listening",
    )
    music_event = router.route_music_phrase_event(
        event_type="PHRASE_PLAYED",
        current_phase="exercise_selection",
        payload={"notes": ["C4", "E4", "G4"]},
    )

    assert tool_event.intent == "TOOL_ANALYSIS_READY"
    assert tool_event.recommended_transition == "analysis"
    assert music_event.intent == "PLAYED_PHRASE"
    assert music_event.entities["notes"] == ["C4", "E4", "G4"]
