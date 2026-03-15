"""Deterministic reference-resolution tool for starter live tutoring flows."""

from __future__ import annotations

import re
from typing import Any

from .registry import ToolSpec

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_NORMALIZATION_RE = re.compile(r"[.]+")
_BIBLE_REFERENCE_RE = re.compile(
    r"^\s*(?:[1-3]\s*)?[A-Za-z][A-Za-z.\s]+?\s+\d+:\d+(?:[-,]\d+)?\s*$",
    re.IGNORECASE,
)
_CLASSICAL_REFERENCE_RE = re.compile(
    r"^\s*[A-Za-z][A-Za-z.\s]+?\s+\d+\.\d+(?:[-,]\d+)?\s*$",
    re.IGNORECASE,
)

_BOOK_ALIASES = {
    "mk": "mark",
    "mrk": "mark",
    "mark": "mark",
    "jn": "john",
    "jhn": "john",
    "john": "john",
    "iliad": "iliad",
    "homer iliad": "iliad",
}

_STARTER_REFERENCE_LIBRARY: dict[str, dict[str, str]] = {
    "mark 1:1": {
        "work": "Gospel of Mark",
        "source": "starter_corpus",
        "passage_kind": "scripture",
        "greek_text": "Αρχη του ευαγγελιου Ιησου Χριστου υιου θεου.",
        "translation": "The beginning of the gospel of Jesus Christ, Son of God.",
    },
    "john 1:1": {
        "work": "Gospel of John",
        "source": "starter_corpus",
        "passage_kind": "scripture",
        "greek_text": "Εν αρχη ην ο λογος, και ο λογος ην προς τον θεον, και θεος ην ο λογος.",
        "translation": "In the beginning was the Word, and the Word was with God, and the Word was God.",
    },
    "iliad 1.1": {
        "work": "Homer, Iliad",
        "source": "starter_corpus",
        "passage_kind": "classical",
        "greek_text": "Μηνιν αειδε, θεα, Πηληιαδεω Αχιληος.",
        "translation": "Sing, goddess, the wrath of Achilles son of Peleus.",
    },
}


def looks_like_reference_request(text: str) -> bool:
    compact = _compact_text(text)
    if not compact:
        return False
    return bool(_BIBLE_REFERENCE_RE.match(compact) or _CLASSICAL_REFERENCE_RE.match(compact))


def normalize_reference(reference: str, work: str | None = None) -> str:
    compact = _compact_text(reference).lower()
    compact = _PUNCT_NORMALIZATION_RE.sub(".", compact)

    if ":" in compact:
        match = re.match(r"^(?P<book>.+?)\s+(?P<chapter>\d+:\d+(?:[-,]\d+)?)$", compact)
    else:
        match = re.match(r"^(?P<book>.+?)\s+(?P<section>\d+\.\d+(?:[-,]\d+)?)$", compact)

    if not match:
        return compact

    book = _normalize_book_name(match.group("book"), work=work)
    tail = match.groupdict().get("chapter") or match.groupdict().get("section") or ""
    return f"{book} {tail}".strip()


def execute_resolve_reference_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    reference = str(arguments.get("reference", "")).strip()
    if not reference:
        raise ValueError("resolve_reference requires a non-empty 'reference' argument")

    work_value = arguments.get("work")
    work = str(work_value).strip() if work_value is not None else None
    preferred_translation_language_value = arguments.get("preferred_translation_language")
    preferred_translation_language = (
        str(preferred_translation_language_value).strip()
        if preferred_translation_language_value is not None
        else "English"
    )

    normalized_reference = normalize_reference(reference, work=work)
    entry = _STARTER_REFERENCE_LIBRARY.get(normalized_reference)
    if entry is None:
        return {
            "tool": "resolve_reference",
            "status": "not_found",
            "reference": reference,
            "normalized_reference": normalized_reference,
            "message": (
                "Could not resolve this reference from the configured starter corpus. "
                "Paste the Greek text or add a corpus-backed reference provider."
            ),
            "next_prompt": "Ask the learner to paste the passage text or show it on camera.",
        }

    return {
        "tool": "resolve_reference",
        "status": "ok",
        "reference": reference,
        "normalized_reference": normalized_reference,
        "work": entry["work"],
        "source": entry["source"],
        "passage_kind": entry["passage_kind"],
        "resolved_text": entry["greek_text"],
        "greek_text": entry["greek_text"],
        "translation": entry["translation"],
        "preferred_translation_language": preferred_translation_language,
        "citation_confidence": "high",
        "next_prompt": "Ask whether the learner wants the tutor to read it aloud or parse the first clause.",
    }


def build_reference_resolution_tool() -> ToolSpec:
    return ToolSpec(
        name="resolve_reference",
        description="Resolve a passage reference into actual source text for live tutoring.",
        notes=(
            "Starter deterministic reference loader for scripture/classical citations. "
            "Successful results should be written into session context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "reference": {"type": "string"},
                "work": {"type": "string"},
                "preferred_translation_language": {"type": "string"},
            },
            "required": ["reference"],
        },
        status="ready",
    )


def _compact_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_book_name(book: str, *, work: str | None = None) -> str:
    compact_book = _compact_text(book).replace(".", "").lower()
    if work:
        work_candidate = _compact_text(work).replace(".", "").lower()
        compact_book = f"{work_candidate} {compact_book}".strip()

    tokens = compact_book.split(" ")
    if len(tokens) >= 2 and tokens[0] in {"1", "2", "3"}:
        key = f"{tokens[0]} {tokens[1]}"
        alias = _BOOK_ALIASES.get(key)
        if alias:
            return alias

    return _BOOK_ALIASES.get(compact_book, compact_book)
