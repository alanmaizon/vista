from __future__ import annotations

from app.domains.music.lesson_orchestrator import LessonOrchestrator


def _lesson_state_events(directive) -> list[dict]:
    return [event for event in directive.events if event.get("type") == "server.lesson_state"]


def test_start_session_enters_intro_phase() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)

    directive = orchestrator.start_session()
    states = _lesson_state_events(directive)

    assert states
    assert states[-1]["phase"] == "intro"
    assert states[-1]["reason"] == "session_started"


def test_goal_capture_transitions_to_exercise_selection() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()

    directive = orchestrator.on_user_text("I want help with D major scale fingering.")
    states = _lesson_state_events(directive)

    assert [state["phase"] for state in states] == ["goal_capture", "exercise_selection"]
    assert states[-1]["captured_goal"] == "I want help with D major scale fingering."
    assert "prepare_lesson" in states[-1]["suggested_actions"]


def test_phrase_check_request_moves_into_listening_and_requests_action() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()
    orchestrator.on_user_text("I want help with A minor.")

    directive = orchestrator.on_user_text("I played a phrase, was that correct?")
    states = _lesson_state_events(directive)
    actions = [event for event in directive.events if event.get("type") == "server.lesson_action"]

    assert states[-1]["phase"] == "listening"
    assert actions
    assert actions[-1]["action"] == "capture_phrase"
    assert actions[-1]["auto"] is True


def test_transcribe_result_emits_analysis_then_feedback_with_card() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()
    orchestrator.on_user_text("I want to practice C major.")
    orchestrator.on_user_text("I played a phrase, was that right?")

    directive = orchestrator.on_tool_result(
        tool_name="transcribe",
        ok=True,
        result={
            "summary": "You rushed the second note; keep quarter-note spacing steady.",
            "confidence": 0.87,
            "notes": [{"note_name": "C4"}, {"note_name": "E4"}, {"note_name": "G4"}],
        },
    )
    phases = [state["phase"] for state in _lesson_state_events(directive)]
    feedback_cards = [event for event in directive.events if event.get("type") == "server.feedback_card"]

    assert phases == ["analysis", "feedback"]
    assert feedback_cards
    assert "You rushed the second note" in feedback_cards[-1]["card"]["summary"]


def test_duplicate_transition_payload_is_deduped() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()
    orchestrator.on_user_text("I need scale help.")

    first = orchestrator.on_user_text("I played a phrase, was that correct?")
    second = orchestrator.on_user_text("I played a phrase, was that correct?")

    assert len(_lesson_state_events(first)) == 1
    assert _lesson_state_events(second) == []


def test_stop_session_moves_to_complete_once() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()

    first = orchestrator.on_session_stopped()
    second = orchestrator.on_session_stopped()

    first_states = _lesson_state_events(first)
    second_states = _lesson_state_events(second)
    assert first_states[-1]["phase"] == "session_complete"
    assert second_states == []


def test_intro_goal_question_routes_to_goal_capture_then_exercise_selection() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()

    directive = orchestrator.on_user_text("Can we work on D minor arpeggios?")
    phases = [state["phase"] for state in _lesson_state_events(directive)]

    assert phases == ["goal_capture", "exercise_selection"]
    assert orchestrator.captured_goal == "Can we work on D minor arpeggios?"


def test_repeat_request_in_feedback_moves_back_to_listening() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()
    orchestrator.on_user_text("Help me with C major.")
    orchestrator.on_user_text("I played a phrase, was that correct?")
    orchestrator.on_tool_result(
        tool_name="transcribe",
        ok=True,
        result={
            "summary": "You rushed the second note.",
            "confidence": 0.8,
            "notes": [{"note_name": "C4"}, {"note_name": "E4"}],
        },
    )

    directive = orchestrator.on_user_text("one more time")
    states = _lesson_state_events(directive)
    actions = [event for event in directive.events if event.get("type") == "server.lesson_action"]

    assert states[-1]["phase"] == "listening"
    assert states[-1]["reason"] == "repeat_requested"
    assert actions[-1]["action"] == "capture_phrase"
    assert actions[-1]["auto"] is False


def test_silence_timeout_event_routes_to_next_step() -> None:
    orchestrator = LessonOrchestrator(skill="GUIDED_LESSON", goal=None)
    orchestrator.start_session()
    orchestrator.on_user_text("Help me with G major.")

    directive = orchestrator.on_music_phrase_event(event_type="SILENCE_TIMEOUT", payload={"timeout_seconds": 10})
    states = _lesson_state_events(directive)

    assert states[-1]["phase"] == "next_step"
    assert states[-1]["reason"] == "silence_timeout"
