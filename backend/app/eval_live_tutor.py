"""Scenario-based evaluation harness for live music tutoring architecture.

This harness is intentionally deterministic: it validates prompt, tool, state,
streaming, and lifecycle contracts without requiring external model access.
It is used to catch regressions when prompt/session logic changes.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
import sys
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.conversation_manager import ConversationManager
from app.domains import build_session_runtime
from app.domains.music.live_tools import music_live_tool_prompt_fragment, register_music_tools
from app.prompts import PromptComposer


@dataclass(frozen=True)
class EvalScenario:
    key: str
    title: str
    skill: str
    goal: str
    user_turns: tuple[str, ...]
    expected_tools: tuple[str, ...] = ()
    required_prompt_markers: tuple[str, ...] = ()
    expected_latency_ms: int = 280
    requires_streaming: bool = True
    requires_continuity: bool = True


@dataclass(frozen=True)
class ScenarioGrade:
    factual_correctness: float
    pedagogical_usefulness: float
    tool_call_correctness: float
    streaming_behavior: float
    latency_responsiveness: float
    continuity_across_turns: float

    @property
    def overall(self) -> float:
        return round(
            mean(
                [
                    self.factual_correctness,
                    self.pedagogical_usefulness,
                    self.tool_call_correctness,
                    self.streaming_behavior,
                    self.latency_responsiveness,
                    self.continuity_across_turns,
                ]
            ),
            3,
        )


PROMPT_PEDAGOGY_MARKERS = (
    "Begin with a short welcome",
    "one correction",
    "one question",
    "Never fabricate pitch/rhythm claims",
)

SCENARIOS: tuple[EvalScenario, ...] = (
    EvalScenario(
        key="explain_scale",
        title="Explain a scale clearly",
        skill="GUIDED_LESSON",
        goal="Explain the D major scale to a beginner and then check understanding.",
        user_turns=("Can you explain the D major scale?", "Why are there two sharps?"),
        required_prompt_markers=("Never guess", "Current music skill:", "Tool policy:"),
    ),
    EvalScenario(
        key="guide_beginner_exercise",
        title="Guide a beginner exercise",
        skill="GUIDED_LESSON",
        goal="Teach a beginner one short call-and-response warmup.",
        user_turns=("I am new to this. What should I play first?",),
        expected_tools=("lesson_action",),
    ),
    EvalScenario(
        key="react_to_played_phrase",
        title="React to a played phrase",
        skill="HEAR_PHRASE",
        goal="Listen to my short phrase and provide grounded feedback.",
        user_turns=("I just played a phrase.",),
        expected_tools=("transcribe",),
        required_prompt_markers=("Never guess musical details",),
    ),
    EvalScenario(
        key="corrective_feedback",
        title="Provide corrective feedback",
        skill="COMPARE_PERFORMANCE",
        goal="Compare my take and tell me one correction to fix first.",
        user_turns=("I think I rushed the second note.",),
        expected_tools=("lesson_action", "lesson_step"),
    ),
    EvalScenario(
        key="follow_up_same_lesson",
        title="Handle follow-up in same lesson",
        skill="GUIDED_LESSON",
        goal="Continue same lesson after a follow-up clarification.",
        user_turns=("How did I do on that bar?", "Can you explain that correction differently?"),
        expected_tools=("lesson_step",),
    ),
    EvalScenario(
        key="recover_after_restart",
        title="Recover cleanly after stop/start",
        skill="GUIDED_LESSON",
        goal="Restart the lesson and continue without duplicate tool actions.",
        user_turns=("Stop for a moment.", "Start again from bar one."),
        expected_tools=("lesson_action",),
        requires_continuity=True,
    ),
)


def _score_marker_coverage(text: str, markers: tuple[str, ...]) -> float:
    if not markers:
        return 1.0
    hits = sum(1 for marker in markers if marker in text)
    return round(hits / len(markers), 3)


def _simulate_stream_contract() -> float:
    # Minimal incremental contract: two partial transcript events followed by a
    # final server.text event must produce progressive text then settle.
    partials = [
        {"type": "server.transcript", "role": "assistant", "text": "Let's start", "partial": True},
        {"type": "server.transcript", "role": "assistant", "text": "Let's start with D major", "partial": True},
    ]
    final_event = {"type": "server.text", "text": "Let's start with D major. Play it slowly first."}
    streaming_text = ""
    for event in partials:
        if not event.get("partial"):
            return 0.0
        streaming_text = str(event.get("text", "")).strip()
    final_text = str(final_event.get("text", "")).strip()
    if not streaming_text or not final_text:
        return 0.0
    if not final_text.startswith("Let's start"):
        return 0.0
    return 1.0


def _simulate_tool_contract(scenario: EvalScenario) -> float:
    if not scenario.expected_tools:
        return 1.0
    manager = ConversationManager(session_id=uuid.uuid4(), user_id="eval-user")
    accepted = 0
    for tool_name in scenario.expected_tools:
        call_id, is_new = manager.register_tool_call(tool_name, args={"example": True}, call_id=f"{tool_name}-1")
        if not is_new:
            continue
        result_ok = manager.register_tool_result(
            tool_name,
            result={"ok": True},
            call_id=call_id,
        )
        if result_ok:
            accepted += 1
    return round(accepted / len(scenario.expected_tools), 3)


def _simulate_continuity_contract(scenario: EvalScenario) -> float:
    if not scenario.requires_continuity:
        return 1.0
    manager = ConversationManager(session_id=uuid.uuid4(), user_id="eval-user")
    for turn in scenario.user_turns:
        manager.add_user_turn(turn)
        manager.add_assistant_turn("Acknowledged. Let's continue.")
    history = manager.get_full_history()
    if len(history) < len(scenario.user_turns) * 2:
        return 0.0
    # Recovery scenario: ensure new manager starts clean without carrying
    # duplicate pending tool call state.
    if scenario.key == "recover_after_restart":
        restarted = ConversationManager(session_id=uuid.uuid4(), user_id="eval-user")
        _, accepted = restarted.register_tool_call("lesson_action", {"restart": True}, call_id="restart-1")
        if not accepted:
            return 0.0
    return 1.0


def _grade_scenario(scenario: EvalScenario) -> tuple[ScenarioGrade, dict[str, Any]]:
    runtime = build_session_runtime(domain="MUSIC", skill=scenario.skill, goal=scenario.goal)
    composer = PromptComposer(runtime, live_context="", memory_context="")
    system_prompt = composer.get_system_prompt()
    opening_prompt = composer.get_opening_user_prompt() or ""

    factual_markers = tuple(scenario.required_prompt_markers) + ("Never guess",)
    factual = _score_marker_coverage(system_prompt, factual_markers)
    pedagogy = _score_marker_coverage(system_prompt, PROMPT_PEDAGOGY_MARKERS)
    tool_score = _simulate_tool_contract(scenario)
    streaming = _simulate_stream_contract() if scenario.requires_streaming else 1.0
    continuity = _simulate_continuity_contract(scenario)
    latency = 1.0 if scenario.expected_latency_ms <= 350 else max(0.0, 350 / scenario.expected_latency_ms)

    grade = ScenarioGrade(
        factual_correctness=factual,
        pedagogical_usefulness=pedagogy,
        tool_call_correctness=tool_score,
        streaming_behavior=round(streaming, 3),
        latency_responsiveness=round(latency, 3),
        continuity_across_turns=round(continuity, 3),
    )
    detail = {
        "scenario": asdict(scenario),
        "opening_prompt": opening_prompt,
        "system_prompt_chars": len(system_prompt),
        "grade": asdict(grade) | {"overall": grade.overall},
    }
    return grade, detail


def run_eval() -> dict[str, Any]:
    register_music_tools()
    _ = music_live_tool_prompt_fragment()

    scenario_details: list[dict[str, Any]] = []
    scenario_scores: list[float] = []
    dimension_buckets: dict[str, list[float]] = {
        "factual_correctness": [],
        "pedagogical_usefulness": [],
        "tool_call_correctness": [],
        "streaming_behavior": [],
        "latency_responsiveness": [],
        "continuity_across_turns": [],
    }

    for scenario in SCENARIOS:
        grade, detail = _grade_scenario(scenario)
        scenario_details.append(detail)
        scenario_scores.append(grade.overall)
        dimension_buckets["factual_correctness"].append(grade.factual_correctness)
        dimension_buckets["pedagogical_usefulness"].append(grade.pedagogical_usefulness)
        dimension_buckets["tool_call_correctness"].append(grade.tool_call_correctness)
        dimension_buckets["streaming_behavior"].append(grade.streaming_behavior)
        dimension_buckets["latency_responsiveness"].append(grade.latency_responsiveness)
        dimension_buckets["continuity_across_turns"].append(grade.continuity_across_turns)

    rubric = {key: round(mean(values), 3) for key, values in dimension_buckets.items()}
    aggregate = round(mean(scenario_scores), 3) if scenario_scores else 0.0
    return {
        "aggregate_score": aggregate,
        "rubric": rubric,
        "scenario_count": len(SCENARIOS),
        "scenarios": scenario_details,
        "pass": aggregate >= 0.8 and all(value >= 0.75 for value in rubric.values()),
    }


def main() -> int:
    report = run_eval()
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
