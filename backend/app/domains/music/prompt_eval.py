"""Prompt quality evaluation helpers for Eurydice music sessions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptCheck:
    key: str
    description: str
    required_phrase: str


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

