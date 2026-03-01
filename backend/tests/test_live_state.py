from __future__ import annotations

from app.live.state import DEFAULT_SKILL, LiveSessionState


def test_unknown_skill_falls_back_to_nav_find() -> None:
    state = LiveSessionState(skill="NOT_A_REAL_SKILL", goal="Find the exit")

    assert state.skill == DEFAULT_SKILL
    assert state.risk_mode == "NORMAL"


def test_refuse_skills_start_in_refuse_mode() -> None:
    state = LiveSessionState(skill="TRAFFIC_CROSSING", goal="Cross the street")

    assert state.risk_mode == "REFUSE"
    assert state.completed is True
    assert state.on_connect_events()[0]["state"] == "refuse"
    assert "disallowed" in state.opening_prompt().lower()


def test_caution_skills_start_in_caution_mode() -> None:
    state = LiveSessionState(skill="COOKING_ASSIST", goal="Read the recipe")

    assert state.risk_mode == "CAUTION"
    assert state.on_connect_events()[0]["state"] == "caution"
    assert "CAUTION mode" in state.opening_prompt()


def test_confirm_moves_state_into_verify_phase() -> None:
    state = LiveSessionState(skill="NAV_FIND", goal="Find the exit sign")
    state.phase = "GUIDE"
    state.awaiting_confirmation = True
    state.last_assistant_text = "Take one small step left."

    prompt = state.on_client_confirm()

    assert state.phase == "VERIFY"
    assert state.confirmations == 1
    assert "verify progress" in prompt.lower()


def test_medication_label_read_is_allowed_and_frame_first() -> None:
    state = LiveSessionState(skill="MEDICATION_LABEL_READ", goal="Read the medication label only")

    assert state.risk_mode == "NORMAL"
    assert state.phase == "FRAME"
    assert state.completed is False
    assert "one medication item at a time" in state.opening_prompt().lower()


def test_model_text_marks_completion_for_match_language() -> None:
    state = LiveSessionState(skill="SHOP_VERIFY", goal="Check the cereal")

    events = state.on_model_text("MATCH. This is the correct cereal box.")

    assert events == []
    assert state.phase == "COMPLETE"
    assert state.completed is True


def test_summary_uses_done_when_after_completion() -> None:
    state = LiveSessionState(skill="REORIENT", goal="Help me understand the room")
    state.completed = True
    state.phase = "COMPLETE"

    summary = state.summary_payload()

    assert any("Done when:" in bullet for bullet in summary["bullets"])
    assert any("Baseline risk: R0" in bullet for bullet in summary["bullets"])
