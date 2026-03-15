from __future__ import annotations

from app.domains.music.lesson_replay import LessonReplayHarness, ReplayTrace


def test_replay_trace_handles_phrase_feedback_without_duplicates() -> None:
    harness = LessonReplayHarness()
    trace = ReplayTrace(
        name="phrase-feedback-trace",
        goal=None,
        events=(
            {
                "type": "transcript_chunk",
                "role": "assistant",
                "text": "Welcome to your lesson.",
                "partial": True,
            },
            {
                "type": "transcript_chunk",
                "role": "assistant",
                "text": "Welcome to your lesson. Tell me your goal.",
                "partial": False,
            },
            {"type": "user_message", "text": "Help me with C major scale."},
            {"type": "user_message", "text": "I played a phrase, was that right?"},
            {
                "type": "tool_result",
                "tool_name": "transcribe",
                "ok": True,
                "result": {
                    "summary": "You rushed the final note. Keep quarter-note spacing even.",
                    "confidence": 0.82,
                    "notes": [{"note_name": "C4"}, {"note_name": "E4"}, {"note_name": "G4"}],
                },
            },
            {"type": "user_message", "text": "can you slow down?"},
        ),
    )

    report = harness.run_trace(trace)

    assert "intro" in report.phase_trace
    assert "goal_capture" in report.phase_trace
    assert "exercise_selection" in report.phase_trace
    assert "listening" in report.phase_trace
    assert "analysis" in report.phase_trace
    assert "feedback" in report.phase_trace
    assert report.duplicate_transitions == 0
    assert report.duplicate_feedback_cards == 0
    assert report.action_trace.count("capture_phrase") >= 1
    assert len(report.feedback_summaries) == 1


def test_replay_trace_recovers_cleanly_after_stop_start() -> None:
    harness = LessonReplayHarness()
    trace = ReplayTrace(
        name="stop-start-recovery",
        goal=None,
        events=(
            {"type": "user_message", "text": "Help me with D minor scale."},
            {"type": "session_event", "action": "stop"},
            {"type": "session_event", "action": "start"},
            {"type": "user_message", "text": "Help me with D minor scale."},
            {"type": "user_message", "text": "what should I do next?"},
        ),
    )

    report = harness.run_trace(trace)

    assert report.phase_trace.count("intro") >= 2
    assert report.phase_trace.count("session_complete") == 1
    assert "next_step" in report.phase_trace
    assert report.duplicate_transitions == 0


def test_replay_trace_handles_resume_after_silence_timeout() -> None:
    harness = LessonReplayHarness()
    trace = ReplayTrace(
        name="resume-after-silence",
        goal=None,
        events=(
            {"type": "user_message", "text": "Help me with A major scale."},
            {"type": "music_phrase_event", "event_name": "SILENCE_TIMEOUT"},
            {"type": "user_message", "text": "let me try"},
        ),
    )

    report = harness.run_trace(trace)

    assert "next_step" in report.phase_trace
    assert "listening" in report.phase_trace
    assert report.duplicate_transitions == 0
