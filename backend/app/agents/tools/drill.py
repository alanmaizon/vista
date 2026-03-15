"""Deterministic drill generation tool."""

from __future__ import annotations

from typing import Any

from .registry import ToolSpec


def _select_drill_type(mistake_summary: str, mode: str | None) -> str:
    summary = mistake_summary.lower()
    selected_mode = (mode or "").lower()
    if "case" in summary or "ending" in summary or selected_mode == "morphology_coach":
        return "morphology_repair"
    if "translation" in summary or selected_mode == "translation_support":
        return "translation_repair"
    if "verb" in summary or "tense" in summary:
        return "verb_form_correction"
    return "guided_recall"


def execute_drill_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    mistake_summary = str(arguments.get("mistake_summary", "")).strip()
    if not mistake_summary:
        raise ValueError("generate_drill requires a non-empty 'mistake_summary' argument")

    mode_value = arguments.get("mode")
    mode = str(mode_value).strip() if mode_value is not None else None
    focus_word_value = arguments.get("focus_word")
    focus_word = str(focus_word_value).strip() if focus_word_value is not None else None

    drill_type = _select_drill_type(mistake_summary, mode)
    focus_note = f"Target focus word: {focus_word}." if focus_word else "Target focus word: learner-selected."

    if drill_type == "morphology_repair":
        prompt = "Identify the case-number value of the focus form, then justify it from context."
    elif drill_type == "translation_repair":
        prompt = "Translate the clause literally first, then provide a polished English line."
    elif drill_type == "verb_form_correction":
        prompt = "Parse the finite verb (person, number, tense, voice, mood) before translating."
    else:
        prompt = "Retell the clause meaning in one line, then name one form that supports your reading."

    return {
        "tool": "generate_drill",
        "status": "ok",
        "drill_type": drill_type,
        "mistake_summary": mistake_summary,
        "mode": mode or "guided_reading",
        "focus_note": focus_note,
        "drill": {
            "prompt": prompt,
            "steps": [
                "Step 1: Learner attempts response aloud in one short turn.",
                "Step 2: Tutor checks one target form and asks for a correction.",
                "Step 3: Learner retries the line with corrected form and meaning.",
            ],
            "hints": [
                "Use endings first, then vocabulary.",
                "Do not skip directly to idiomatic English.",
                "Keep each retry under one sentence.",
            ],
            "expected_response_format": "one morphology line + one short translation line",
            "success_criteria": [
                "Target form is identified correctly.",
                "Literal meaning remains aligned with morphology.",
                "Retry is more accurate than first attempt.",
            ],
        },
    }


def build_drill_generation_tool() -> ToolSpec:
    return ToolSpec(
        name="generate_drill",
        description="Create a short follow-up drill from a recent learner mistake.",
        notes="Deterministic micro-drill template generator keyed to mistake type and tutoring mode.",
        input_schema={
            "type": "object",
            "properties": {
                "mistake_summary": {"type": "string"},
                "mode": {"type": "string"},
                "focus_word": {"type": "string"},
            },
            "required": ["mistake_summary"],
        },
        status="ready",
    )
