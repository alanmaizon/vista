"""Prompt quality evaluation helpers for Eurydice music sessions."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


def _normalize_prompt_text(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


@dataclass(frozen=True)
class PromptCheck:
    key: str
    description: str
    required_phrase: str


@dataclass(frozen=True)
class PromptCapability:
    key: str
    description: str
    markers: tuple[str, ...]
    category: str = "functionality"


@dataclass(frozen=True)
class PromptScenario:
    key: str
    title: str
    user_request: str
    required_capabilities: tuple[str, ...]
    reasoning_capabilities: tuple[str, ...] = ()
    notes: str = ""


CORE_PROMPT_CHECKS: tuple[PromptCheck, ...] = (
    PromptCheck(
        key="no_guessing",
        description="Prompt must explicitly forbid guessing musical details.",
        required_phrase="Never guess",
    ),
    PromptCheck(
        key="single_step_guidance",
        description="Prompt must enforce one instruction at a time.",
        required_phrase="one musical instruction",
    ),
    PromptCheck(
        key="confidence_signaling",
        description="Prompt must ask for explicit confidence/uncertainty handling.",
        required_phrase="If confidence is limited",
    ),
    PromptCheck(
        key="verification_loop",
        description="Prompt must require verification before final claims.",
        required_phrase="Verify before claiming",
    ),
)

CAPABILITY_CHECKS: tuple[PromptCapability, ...] = (
    PromptCapability(
        key="sheet_frame_coach",
        description="Coach the user to frame a clear score region.",
        markers=("SHEET_FRAME_COACH", "frame one stave", "better score view"),
    ),
    PromptCapability(
        key="read_score",
        description="Read visible notation from a score.",
        markers=("READ_SCORE", "describe visible notation"),
    ),
    PromptCapability(
        key="hear_phrase",
        description="Identify a melody, interval, chord, or arpeggio from live audio.",
        markers=("HEAR_PHRASE", "identify a melody", "identify a melody, chord, interval, or arpeggio"),
    ),
    PromptCapability(
        key="compare_performance",
        description="Compare a performed phrase against an intended phrase or score.",
        markers=("COMPARE_PERFORMANCE", "compare what was played against the intended notes or rhythm"),
    ),
    PromptCapability(
        key="ear_train",
        description="Run a focused ear-training drill.",
        markers=("EAR_TRAIN", "one listening drill at a time"),
    ),
    PromptCapability(
        key="generate_example",
        description="Generate a labelled original phrase or exercise.",
        markers=("GENERATE_EXAMPLE", "label it clearly as generated"),
    ),
    PromptCapability(
        key="guided_lesson_tools",
        description="Use deterministic lesson tools when structured score or lesson data is needed.",
        markers=(
            '"name":"lesson_action"',
            "lesson_action, lesson_step, render_score",
            "deterministic score/lesson data",
        ),
    ),
    PromptCapability(
        key="no_guessing",
        description="Refuse to guess uncertain musical facts.",
        markers=("Never guess",),
        category="reasoning",
    ),
    PromptCapability(
        key="single_step_guidance",
        description="Give only one musical instruction at a time.",
        markers=("one musical instruction",),
        category="reasoning",
    ),
    PromptCapability(
        key="confidence_signaling",
        description="Expose confidence limits and uncertainty explicitly.",
        markers=("If confidence is limited", "say what is uncertain"),
        category="reasoning",
    ),
    PromptCapability(
        key="observation_vs_inference",
        description="Separate observation, inference, and verification state.",
        markers=("what you heard, what you inferred, and what still needs verification",),
        category="reasoning",
    ),
    PromptCapability(
        key="verification_loop",
        description="Require verification before final musical claims.",
        markers=("Verify before claiming", "Summarize what was confirmed, what remains uncertain"),
        category="reasoning",
    ),
    PromptCapability(
        key="replay_recovery",
        description="Request narrower retries when evidence is noisy or unresolved.",
        markers=("ask for a replay", "ask for a simpler replay", "ask for a better score view"),
        category="reasoning",
    ),
    PromptCapability(
        key="live_evidence_priority",
        description="Treat stored context as supporting material and prioritize live evidence.",
        markers=("Prioritize live audio/video evidence", "supporting context only"),
        category="reasoning",
    ),
)

DEFAULT_EVAL_SCENARIOS: tuple[PromptScenario, ...] = (
    PromptScenario(
        key="camera_score_reading",
        title="Camera-based score reading",
        user_request="Read one visible bar from my score and tell me what is on it.",
        required_capabilities=("sheet_frame_coach", "read_score"),
        reasoning_capabilities=("verification_loop", "replay_recovery"),
        notes="Should coach framing before claiming notation when the score is unclear.",
    ),
    PromptScenario(
        key="phrase_identification",
        title="Live phrase identification",
        user_request="I just played four notes. Identify the arpeggio without guessing.",
        required_capabilities=("hear_phrase",),
        reasoning_capabilities=("no_guessing", "confidence_signaling", "verification_loop"),
        notes="Should avoid inventing pitch content and ask for a replay if confidence is weak.",
    ),
    PromptScenario(
        key="performance_comparison",
        title="Score-to-performance comparison",
        user_request="Compare my take against the current bar and explain the mismatch.",
        required_capabilities=("compare_performance", "guided_lesson_tools"),
        reasoning_capabilities=("observation_vs_inference", "single_step_guidance"),
        notes="Should leverage deterministic lesson data instead of relying only on free-form inference.",
    ),
    PromptScenario(
        key="ear_training",
        title="One-step ear training drill",
        user_request="Give me one interval drill and verify my answer after I respond.",
        required_capabilities=("ear_train",),
        reasoning_capabilities=("single_step_guidance", "verification_loop"),
    ),
    PromptScenario(
        key="generated_example",
        title="Generated exercise phrase",
        user_request="Create a short exercise phrase for me to practice and mark it as generated.",
        required_capabilities=("generate_example",),
        reasoning_capabilities=("single_step_guidance",),
    ),
)


def evaluate_prompt_quality(prompt: str) -> dict[str, object]:
    """Evaluate prompt coverage against baseline quality checks."""
    normalized = prompt or ""
    results: list[dict[str, object]] = []
    passed = 0

    for check in CORE_PROMPT_CHECKS:
        ok = check.required_phrase in normalized
        if ok:
            passed += 1
        results.append(
            {
                "key": check.key,
                "description": check.description,
                "required_phrase": check.required_phrase,
                "passed": ok,
            }
        )

    score = passed / len(CORE_PROMPT_CHECKS) if CORE_PROMPT_CHECKS else 1.0
    return {
        "score": round(score, 3),
        "passed": passed,
        "total": len(CORE_PROMPT_CHECKS),
        "checks": results,
    }


def evaluate_prompt_capabilities(prompt: str) -> dict[str, object]:
    """Evaluate functional and reasoning capability coverage for a prompt bundle."""
    normalized = prompt or ""
    reports: list[dict[str, object]] = []
    passed = 0

    for capability in CAPABILITY_CHECKS:
        matched_marker = next((marker for marker in capability.markers if marker in normalized), "")
        ok = bool(matched_marker)
        if ok:
            passed += 1
        reports.append(
            {
                "key": capability.key,
                "description": capability.description,
                "category": capability.category,
                "markers": capability.markers,
                "matched_marker": matched_marker,
                "passed": ok,
            }
        )

    score = passed / len(CAPABILITY_CHECKS) if CAPABILITY_CHECKS else 1.0
    return {
        "score": round(score, 3),
        "passed": passed,
        "total": len(CAPABILITY_CHECKS),
        "checks": reports,
    }


def _capability_report_map(reports: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(report["key"]): report for report in reports}


def evaluate_prompt_scenarios(
    prompt: str,
    *,
    scenarios: tuple[PromptScenario, ...] = DEFAULT_EVAL_SCENARIOS,
) -> dict[str, object]:
    """Score the prompt against concrete user scenarios and reasoning expectations."""
    capability_eval = evaluate_prompt_capabilities(prompt)
    capability_map = _capability_report_map(list(capability_eval["checks"]))

    scenario_reports: list[dict[str, object]] = []
    scores: list[float] = []

    for scenario in scenarios:
        matched_required = [
            capability_key
            for capability_key in scenario.required_capabilities
            if capability_map.get(capability_key, {}).get("passed")
        ]
        missing_required = [
            capability_key
            for capability_key in scenario.required_capabilities
            if capability_key not in matched_required
        ]
        matched_reasoning = [
            capability_key
            for capability_key in scenario.reasoning_capabilities
            if capability_map.get(capability_key, {}).get("passed")
        ]
        missing_reasoning = [
            capability_key
            for capability_key in scenario.reasoning_capabilities
            if capability_key not in matched_reasoning
        ]

        total_checks = len(scenario.required_capabilities) + len(scenario.reasoning_capabilities)
        passed_checks = len(matched_required) + len(matched_reasoning)
        score = passed_checks / total_checks if total_checks else 1.0
        scores.append(score)

        scenario_reports.append(
            {
                "key": scenario.key,
                "title": scenario.title,
                "user_request": scenario.user_request,
                "score": round(score, 3),
                "required_capabilities": list(scenario.required_capabilities),
                "reasoning_capabilities": list(scenario.reasoning_capabilities),
                "matched_required": matched_required,
                "missing_required": missing_required,
                "matched_reasoning": matched_reasoning,
                "missing_reasoning": missing_reasoning,
                "notes": scenario.notes,
            }
        )

    return {
        "score": round(mean(scores), 3) if scores else 1.0,
        "total": len(scenario_reports),
        "scenarios": scenario_reports,
    }


def evaluate_music_agent_prompt(
    system_prompt: str,
    *,
    tool_prompt_fragment: str = "",
    context_policy_fragment: str = "",
    scenarios: tuple[PromptScenario, ...] = DEFAULT_EVAL_SCENARIOS,
) -> dict[str, object]:
    """Run a richer prompt-evaluation suite for the Eurydice music agent."""
    aggregate_prompt = _normalize_prompt_text(system_prompt, tool_prompt_fragment, context_policy_fragment)
    quality = evaluate_prompt_quality(aggregate_prompt)
    capability_eval = evaluate_prompt_capabilities(aggregate_prompt)
    scenario_eval = evaluate_prompt_scenarios(aggregate_prompt, scenarios=scenarios)

    reasoning_checks = [
        check for check in capability_eval["checks"] if check.get("category") == "reasoning"
    ]
    functionality_checks = [
        check for check in capability_eval["checks"] if check.get("category") == "functionality"
    ]
    reasoning_score = (
        mean(1.0 if check["passed"] else 0.0 for check in reasoning_checks) if reasoning_checks else 1.0
    )
    functionality_score = (
        mean(1.0 if check["passed"] else 0.0 for check in functionality_checks)
        if functionality_checks
        else 1.0
    )

    strengths: list[str] = []
    weaknesses: list[str] = []
    for check in capability_eval["checks"]:
        description = str(check["description"])
        if check["passed"]:
            strengths.append(description)
        else:
            weaknesses.append(description)

    aggregate_score = mean(
        [
            float(quality["score"]),
            reasoning_score,
            functionality_score,
            float(scenario_eval["score"]),
        ]
    )

    return {
        "aggregate_score": round(aggregate_score, 3),
        "prompt_quality_score": quality["score"],
        "reasoning_score": round(reasoning_score, 3),
        "functionality_score": round(functionality_score, 3),
        "scenario_score": scenario_eval["score"],
        "quality": quality,
        "capabilities": capability_eval,
        "scenarios": scenario_eval,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "aggregate_prompt": aggregate_prompt,
    }
