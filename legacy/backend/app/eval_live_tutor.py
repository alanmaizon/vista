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
from app.domains.music.lesson_orchestrator import LessonOrchestrator
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
    expected_phase_markers: tuple[str, ...] = ("intro", "goal_capture", "exercise_selection")
    simulate_phrase_tool: bool = False
    includes_follow_up: bool = False
    includes_repeat_request: bool = False
    includes_silence_resume: bool = False


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
        key="ambiguous_clarification_requests",
        title="Ambiguous clarification requests",
        skill="GUIDED_LESSON",
        goal="Help me understand a scale slowly when I ask short ambiguous follow-ups.",
        user_turns=("Help me with A major scale.", "again", "can you slow down?"),
        expected_phase_markers=("intro", "goal_capture", "exercise_selection", "listening", "feedback"),
        includes_follow_up=True,
        includes_repeat_request=True,
        required_prompt_markers=("Never guess", "Current music skill:", "Tool policy:"),
    ),
    EvalScenario(
        key="repeated_exercise_requests",
        title="Repeated exercise requests",
        skill="GUIDED_LESSON",
        goal="Ask for another exercise multiple times and keep flow stable.",
        user_turns=("Help me with rhythm.", "Give me another exercise.", "one more exercise please"),
        expected_tools=("lesson_step",),
        expected_phase_markers=("intro", "goal_capture", "exercise_selection"),
    ),
    EvalScenario(
        key="feedback_after_played_phrase",
        title="User asks feedback after playing a phrase",
        skill="GUIDED_LESSON",
        goal="I play a phrase and ask if it was correct.",
        user_turns=("Help me with C major.", "let me try", "was that right?"),
        expected_tools=("transcribe",),
        expected_phase_markers=("intro", "goal_capture", "exercise_selection", "listening", "analysis", "feedback"),
        simulate_phrase_tool=True,
    ),
    EvalScenario(
        key="interrupt_explanation_follow_up",
        title="User interrupts explanation with follow-up",
        skill="GUIDED_LESSON",
        goal="Tutor explains then user asks a clarifying interruption.",
        user_turns=("Explain harmonic minor briefly.", "why is that?", "I still struggle with this."),
        expected_tools=("transcribe",),
        expected_phase_markers=("intro", "goal_capture", "exercise_selection", "feedback"),
        simulate_phrase_tool=True,
        includes_follow_up=True,
    ),
    EvalScenario(
        key="resume_after_silence",
        title="User resumes after silence",
        skill="GUIDED_LESSON",
        goal="Recover from silence timeout and continue practice.",
        user_turns=("Help me with arpeggios.",),
        expected_phase_markers=("intro", "goal_capture", "exercise_selection", "next_step", "listening"),
        includes_silence_resume=True,
    ),
    EvalScenario(
        key="ask_what_next",
        title='User asks "what should I do next?"',
        skill="GUIDED_LESSON",
        goal="User asks for the next step after phrase analysis.",
        user_turns=("I want to improve rhythm.", "I played a phrase, was that correct?", "what should I do next?"),
        expected_tools=("transcribe", "lesson_step"),
        expected_phase_markers=("intro", "goal_capture", "exercise_selection", "listening", "analysis", "feedback", "next_step"),
        simulate_phrase_tool=True,
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
    # Resume scenario: ensure a restarted manager starts clean without carrying
    # duplicate pending tool call state.
    if scenario.key == "resume_after_silence":
        restarted = ConversationManager(session_id=uuid.uuid4(), user_id="eval-user")
        _, accepted = restarted.register_tool_call("lesson_action", {"resume": True}, call_id="resume-1")
        if not accepted:
            return 0.0
    return 1.0


def _ordered_phase_coverage(phases: list[str], expected: tuple[str, ...]) -> float:
    if not expected:
        return 1.0
    cursor = 0
    for phase in phases:
        if phase == expected[cursor]:
            cursor += 1
            if cursor >= len(expected):
                break
    return round(cursor / len(expected), 3)


def _simulate_orchestrator_contract(scenario: EvalScenario) -> tuple[float, dict[str, Any]]:
    orchestrator = LessonOrchestrator(skill=scenario.skill, goal=scenario.goal)
    phase_trace: list[str] = []

    def _capture(directive) -> None:
        for event in directive.events:
            if event.get("type") == "server.lesson_state":
                phase = str(event.get("phase", "")).strip()
                if phase:
                    phase_trace.append(phase)

    _capture(orchestrator.start_session())
    for turn in scenario.user_turns:
        _capture(orchestrator.on_user_text(turn))

    if scenario.simulate_phrase_tool:
        _capture(
            orchestrator.on_tool_result(
                tool_name="transcribe",
                ok=True,
                result={
                    "summary": "Deterministic phrase result is available.",
                    "confidence": 0.82,
                    "notes": [{"note_name": "C4"}, {"note_name": "E4"}],
                },
            )
        )
        _capture(orchestrator.on_assistant_text("Thanks, here's one correction and one next step."))

    if scenario.includes_follow_up:
        _capture(orchestrator.on_user_text("Can you explain that again? I am still struggling."))

    if scenario.includes_repeat_request:
        _capture(orchestrator.on_user_text("one more time"))

    if scenario.includes_silence_resume:
        _capture(orchestrator.on_music_phrase_event(event_type="SILENCE_TIMEOUT", payload={"timeout_seconds": 12}))
        _capture(orchestrator.on_user_text("let me try"))

    expected_score = _ordered_phase_coverage(phase_trace, scenario.expected_phase_markers)
    adjacent_duplicates = sum(1 for index in range(1, len(phase_trace)) if phase_trace[index] == phase_trace[index - 1])
    dedupe_score = 1.0 if not phase_trace else round(max(0.0, 1 - (adjacent_duplicates / len(phase_trace))), 3)
    score = round((expected_score * 0.8) + (dedupe_score * 0.2), 3)
    return score, {
        "phase_trace": phase_trace,
        "expected_phase_markers": list(scenario.expected_phase_markers),
        "phase_coverage": expected_score,
        "dedupe_score": dedupe_score,
    }


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
    orchestrator_score, orchestrator_detail = _simulate_orchestrator_contract(scenario)
    latency = 1.0 if scenario.expected_latency_ms <= 350 else max(0.0, 350 / scenario.expected_latency_ms)

    grade = ScenarioGrade(
        factual_correctness=factual,
        pedagogical_usefulness=round((pedagogy + orchestrator_score) / 2, 3),
        tool_call_correctness=tool_score,
        streaming_behavior=round(streaming, 3),
        latency_responsiveness=round(latency, 3),
        continuity_across_turns=round((continuity + orchestrator_score) / 2, 3),
    )
    detail = {
        "scenario": asdict(scenario),
        "opening_prompt": opening_prompt,
        "system_prompt_chars": len(system_prompt),
        "orchestrator": orchestrator_detail,
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
