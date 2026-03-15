"""Deterministic response grading tool."""

from __future__ import annotations

import difflib
import re
from collections import Counter
from typing import Any

from .registry import ToolSpec


def _normalize_text(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^0-9a-zA-Z\u0370-\u03ff\s]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _tokenize(value: str) -> list[str]:
    normalized = _normalize_text(value)
    return [token for token in normalized.split(" ") if token]


def _token_delta(learner_tokens: list[str], reference_tokens: list[str]) -> tuple[list[str], list[str]]:
    learner_counter = Counter(learner_tokens)
    reference_counter = Counter(reference_tokens)

    missing: list[str] = []
    extras: list[str] = []

    for token, count in reference_counter.items():
        delta = count - learner_counter.get(token, 0)
        if delta > 0:
            missing.extend([token] * delta)
    for token, count in learner_counter.items():
        delta = count - reference_counter.get(token, 0)
        if delta > 0:
            extras.extend([token] * delta)
    return missing, extras


def _band_for_score(score: int) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 55:
        return "developing"
    return "needs_work"


def execute_grade_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    learner_answer = str(arguments.get("learner_answer", "")).strip()
    if not learner_answer:
        raise ValueError("grade_attempt requires a non-empty 'learner_answer' argument")

    reference_answer_arg = arguments.get("reference_answer")
    reference_answer = str(reference_answer_arg).strip() if reference_answer_arg is not None else ""

    learner_norm = _normalize_text(learner_answer)
    reference_norm = _normalize_text(reference_answer)
    learner_tokens = _tokenize(learner_answer)
    reference_tokens = _tokenize(reference_answer)

    if reference_norm:
        similarity_ratio = difflib.SequenceMatcher(a=learner_norm, b=reference_norm).ratio()
        overlap = (
            len(set(learner_tokens).intersection(reference_tokens)) / max(len(set(reference_tokens)), 1)
        )
        score = round((similarity_ratio * 0.7 + overlap * 0.3) * 100)
        missing_tokens, extra_tokens = _token_delta(learner_tokens, reference_tokens)
    else:
        similarity_ratio = 0.0
        overlap = 0.0
        score = 0
        missing_tokens = []
        extra_tokens = []

    band = _band_for_score(score)
    if not reference_norm:
        feedback = "No reference answer was provided, so only a capture of the learner answer is available."
    elif band in {"excellent", "good"}:
        feedback = "Strong alignment with the reference. Keep precision on endings and word order."
    elif band == "developing":
        feedback = "Core meaning is present, but morphology or key tokens still need correction."
    else:
        feedback = "Major gaps remain. Focus on one clause and verify each form before translating."

    return {
        "tool": "grade_attempt",
        "status": "ok" if reference_norm else "needs_reference",
        "score": score,
        "band": band,
        "similarity_ratio": round(similarity_ratio, 3),
        "token_overlap": round(overlap, 3),
        "missing_tokens": missing_tokens[:8],
        "extra_tokens": extra_tokens[:8],
        "feedback": feedback,
        "next_prompt": "Ask the learner to retry only the missing phrase before full re-attempt.",
    }


def build_grade_response_tool() -> ToolSpec:
    return ToolSpec(
        name="grade_attempt",
        description="Evaluate how close the learner's spoken or typed answer is to the target reading or translation.",
        notes="Deterministic lexical overlap and sequence scoring for fast formative feedback.",
        input_schema={
            "type": "object",
            "properties": {
                "learner_answer": {"type": "string"},
                "reference_answer": {"type": "string"},
            },
            "required": ["learner_answer"],
        },
        status="ready",
    )
