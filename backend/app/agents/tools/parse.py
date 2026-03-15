"""Deterministic parsing tool for early Ancient Greek tutoring loops."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .registry import ToolSpec


def _strip_diacritics(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )


def _normalize_token(token: str) -> str:
    cleaned = _strip_diacritics(token).lower()
    cleaned = cleaned.replace("ς", "σ")
    return re.sub(r"[^0-9a-zA-Z\u0370-\u03ff]+", "", cleaned)


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[^\s]+", text) if token.strip()]


def _choose_focus_token(tokens: list[str], focus_word: str | None) -> tuple[str, int]:
    if not tokens:
        return "", -1
    if not focus_word:
        return tokens[0], 0

    normalized_focus = _normalize_token(focus_word)
    for index, token in enumerate(tokens):
        if _normalize_token(token) == normalized_focus:
            return token, index
    return focus_word, -1


def _match_ending(value: str, endings: dict[str, dict[str, str]]) -> dict[str, str] | None:
    for ending, payload in endings.items():
        if value.endswith(ending):
            return payload
    return None


def _guess_analysis(focus_word: str) -> dict[str, Any]:
    normalized = _normalize_token(focus_word)

    noun_endings = {
        "os": {"part_of_speech": "noun_or_adjective", "case": "nominative", "number": "singular"},
        "on": {"part_of_speech": "noun_or_adjective", "case": "accusative", "number": "singular"},
        "ou": {"part_of_speech": "noun_or_adjective", "case": "genitive", "number": "singular"},
        "oi": {"part_of_speech": "noun_or_adjective", "case": "nominative", "number": "plural"},
        "ous": {"part_of_speech": "noun_or_adjective", "case": "accusative", "number": "plural"},
        "wn": {"part_of_speech": "noun_or_adjective", "case": "genitive", "number": "plural"},
        "h": {"part_of_speech": "noun_or_adjective", "case": "nominative", "number": "singular"},
        "hs": {"part_of_speech": "noun_or_adjective", "case": "genitive", "number": "singular"},
        "ai": {"part_of_speech": "noun_or_adjective", "case": "nominative", "number": "plural"},
        "as": {"part_of_speech": "noun_or_adjective", "case": "accusative", "number": "plural"},
    }
    verb_endings = {
        "w": {"part_of_speech": "verb", "person": "first", "number": "singular", "tense": "present"},
        "eis": {
            "part_of_speech": "verb",
            "person": "second",
            "number": "singular",
            "tense": "present",
        },
        "ei": {"part_of_speech": "verb", "person": "third", "number": "singular", "tense": "present"},
        "omen": {"part_of_speech": "verb", "person": "first", "number": "plural", "tense": "present"},
        "ete": {"part_of_speech": "verb", "person": "second", "number": "plural", "tense": "present"},
        "ousi": {"part_of_speech": "verb", "person": "third", "number": "plural", "tense": "present"},
        "ein": {"part_of_speech": "verb", "mood": "infinitive", "tense": "present"},
        "sa": {"part_of_speech": "verb", "tense_hint": "aorist_marker"},
    }

    noun_guess = _match_ending(normalized, noun_endings)
    verb_guess = _match_ending(normalized, verb_endings)

    if verb_guess:
        return {"confidence": "low", **verb_guess}
    if noun_guess:
        return {"confidence": "low", **noun_guess}
    return {
        "part_of_speech": "unknown",
        "confidence": "low",
    }


def execute_parse_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    text = str(arguments.get("text", "")).strip()
    if not text:
        raise ValueError("parse_passage requires a non-empty 'text' argument")

    focus_word_arg = arguments.get("focus_word")
    focus_word = str(focus_word_arg).strip() if focus_word_arg is not None else None

    tokens = _tokenize(text)
    focus_token, focus_index = _choose_focus_token(tokens, focus_word)
    analysis = _guess_analysis(focus_token)

    syntax_hints = [
        "Find the finite verb first and anchor clause structure around it.",
        "Check whether the focus form agrees with a nearby noun or adjective.",
        "Use case ending clues before committing to translation order.",
    ]

    return {
        "tool": "parse_passage",
        "status": "ok",
        "focus_word": focus_token,
        "focus_index": focus_index,
        "token_count": len(tokens),
        "analysis": analysis,
        "syntax_hints": syntax_hints,
        "translation_hint": (
            "Build a literal gloss first, then smooth the English only after the morphology is settled."
        ),
        "next_prompt": "Ask the learner to explain the focus word's role in the clause.",
    }


def build_parse_tool() -> ToolSpec:
    return ToolSpec(
        name="parse_passage",
        description="Break a learner-selected Greek word or clause into morphology and syntax hints.",
        notes="Deterministic starter analysis using suffix heuristics and clause-level tutoring hints.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "focus_word": {"type": "string"},
            },
            "required": ["text"],
        },
        status="ready",
    )
