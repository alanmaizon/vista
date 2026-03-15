from __future__ import annotations

from app.domains.music.constitution import DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS
from app.domains.music.live_tools import music_live_tool_prompt_fragment
from app.domains.music.prompt_eval import evaluate_music_agent_prompt, evaluate_prompt_quality


def test_default_music_prompt_passes_core_quality_checks() -> None:
    report = evaluate_prompt_quality(DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS)

    assert report["score"] == 1.0
    assert report["passed"] == report["total"]


def test_prompt_quality_flags_missing_core_requirements() -> None:
    report = evaluate_prompt_quality("You are a music helper.")

    assert report["score"] < 1.0
    failed = [check for check in report["checks"] if not check["passed"]]
    assert failed


def test_music_agent_prompt_suite_scores_default_prompt_highly() -> None:
    report = evaluate_music_agent_prompt(
        DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS,
        tool_prompt_fragment=music_live_tool_prompt_fragment(),
        context_policy_fragment=(
            "CONTEXT_POLICY: Treat this as supporting context only. "
            "Prioritize live audio/video evidence."
        ),
    )

    assert report["aggregate_score"] >= 0.9
    assert report["reasoning_score"] >= 0.9
    assert report["functionality_score"] >= 0.8
    assert report["scenario_score"] >= 0.9
    assert "Refuse to guess uncertain musical facts." in report["strengths"]
    assert not report["weaknesses"]


def test_music_agent_prompt_suite_surfaces_missing_capabilities() -> None:
    report = evaluate_music_agent_prompt(
        "You are a friendly assistant. Help with music if possible.",
        tool_prompt_fragment="",
        context_policy_fragment="",
    )

    assert report["aggregate_score"] < 0.5
    assert "Use deterministic lesson tools when structured score or lesson data is needed." in report["weaknesses"]
    weak_scenarios = [scenario for scenario in report["scenarios"]["scenarios"] if scenario["score"] < 1.0]
    assert weak_scenarios
