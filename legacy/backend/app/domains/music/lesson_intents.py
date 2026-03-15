"""Typed intent/event routing for guided lesson orchestration.

The router keeps conversation control deterministic and phase-aware:
- deterministic phrase/clarification/stop rules first,
- phase-aware heuristics for ambiguous short follow-ups,
- and a lightweight fallback classifier when rules are inconclusive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


VALID_LESSON_PHASES = {
    "idle",
    "intro",
    "goal_capture",
    "exercise_selection",
    "listening",
    "analysis",
    "feedback",
    "next_step",
    "session_complete",
}

INTENT_LABELS = {
    "ASK_EXPLANATION",
    "REQUEST_EXERCISE",
    "PLAYED_PHRASE",
    "ASK_FEEDBACK",
    "CONFUSED_FOLLOWUP",
    "READY_FOR_NEXT_STEP",
    "REPEAT_REQUEST",
    "STOP_REQUEST",
    "OFF_TOPIC",
    "SILENCE_TIMEOUT",
    "SHARE_GOAL",
    "TOOL_ANALYSIS_READY",
    "TOOL_ANALYSIS_FAILED",
}


_STOP_PATTERNS = (
    re.compile(r"\b(stop|pause|end|finish|quit|done for now)\b"),
    re.compile(r"\bthat's enough\b"),
)
_FEEDBACK_PATTERNS = (
    re.compile(r"\bwas that (right|correct)\b"),
    re.compile(r"\bhow was that\b"),
    re.compile(r"\bdid i play\b"),
    re.compile(r"\bcheck my phrase\b"),
    re.compile(r"\bfeedback\b"),
)
_PHRASE_PATTERNS = (
    re.compile(r"\bi played\b"),
    re.compile(r"\blet me try\b"),
    re.compile(r"\bmy take\b"),
    re.compile(r"\bi'?ll play\b"),
    re.compile(r"\bhere goes\b"),
)
_CONFUSED_PATTERNS = (
    re.compile(r"\bi don't get it\b"),
    re.compile(r"\bconfus(ed|ing)\b"),
    re.compile(r"\bstruggl(e|ing)\b"),
    re.compile(r"\btoo fast\b"),
    re.compile(r"\bslow down\b"),
    re.compile(r"\bhard\b"),
)
_REPEAT_PATTERNS = (
    re.compile(r"\bagain\b"),
    re.compile(r"\bone more time\b"),
    re.compile(r"\brepeat\b"),
)
_NEXT_STEP_PATTERNS = (
    re.compile(r"\bwhat now\b"),
    re.compile(r"\bwhat should i do next\b"),
    re.compile(r"\bnext step\b"),
    re.compile(r"\bwhat next\b"),
    re.compile(r"\bready for next\b"),
)
_EXERCISE_PATTERNS = (
    re.compile(r"\bexercise\b"),
    re.compile(r"\bdrill\b"),
    re.compile(r"\bpractice\b"),
    re.compile(r"\bwork on\b"),
)
_EXPLANATION_PATTERNS = (
    re.compile(r"\bwhy\b"),
    re.compile(r"\bhow\b"),
    re.compile(r"\bexplain\b"),
    re.compile(r"\bwhat does\b"),
)
_OFF_TOPIC_PATTERNS = (
    re.compile(r"\bweather\b"),
    re.compile(r"\bpolitic(s|al)\b"),
    re.compile(r"\bmovie(s)?\b"),
)


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _normalize_phase(value: str | None) -> str:
    clean = _normalize_text(value).lower()
    return clean if clean in VALID_LESSON_PHASES else "idle"


def _contains_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


@dataclass(frozen=True)
class LessonRoutingInput:
    """Routing contract for user-text classification."""

    latest_user_transcript: str
    current_phase: str
    recent_conversation_context: tuple[dict[str, Any], ...] = ()
    deterministic_tool_outputs: dict[str, Any] | None = None
    music_phrase_events: tuple[dict[str, Any], ...] = ()
    session_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RoutedLessonEvent:
    """Typed event output consumed by the lesson orchestrator."""

    intent: str
    confidence: float
    source: str
    current_phase: str
    recommended_transition: str | None
    entities: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "source": self.source,
            "current_phase": self.current_phase,
            "recommended_transition": self.recommended_transition,
            "entities": self.entities,
        }


class LessonIntentRouter:
    """Hybrid deterministic + heuristic router for guided lesson events."""

    def route_user_input(self, routing_input: LessonRoutingInput) -> RoutedLessonEvent:
        text = _normalize_text(routing_input.latest_user_transcript)
        phase = _normalize_phase(routing_input.current_phase)
        lower = text.lower()
        metadata = routing_input.session_metadata or {}

        if metadata.get("silence_timeout") is True:
            return self._event(
                intent="SILENCE_TIMEOUT",
                confidence=0.99,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="next_step",
                entities={"timeout_seconds": metadata.get("timeout_seconds")},
            )

        if not text:
            return self._event(
                intent="OFF_TOPIC",
                confidence=0.4,
                source="fallback_classifier",
                phase=phase,
                recommended_transition=None,
            )

        if _contains_any(lower, _STOP_PATTERNS):
            return self._event(
                intent="STOP_REQUEST",
                confidence=0.99,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="session_complete",
            )
        if phase in {"intro", "goal_capture"}:
            return self._event(
                intent="SHARE_GOAL",
                confidence=0.84,
                source="phase_heuristic",
                phase=phase,
                recommended_transition="exercise_selection",
                entities={"goal_text": text},
            )
        if _contains_any(lower, _FEEDBACK_PATTERNS):
            return self._event(
                intent="ASK_FEEDBACK",
                confidence=0.93,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="listening",
                entities={"feedback_target": "phrase"},
            )
        if _contains_any(lower, _PHRASE_PATTERNS):
            return self._event(
                intent="PLAYED_PHRASE",
                confidence=0.91,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="listening",
            )
        if _contains_any(lower, _CONFUSED_PATTERNS):
            return self._event(
                intent="CONFUSED_FOLLOWUP",
                confidence=0.9,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="feedback",
            )
        if _contains_any(lower, _REPEAT_PATTERNS):
            return self._event(
                intent="REPEAT_REQUEST",
                confidence=0.88,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="listening" if phase in {"listening", "analysis", "feedback", "next_step"} else None,
            )
        if _contains_any(lower, _NEXT_STEP_PATTERNS):
            return self._event(
                intent="READY_FOR_NEXT_STEP",
                confidence=0.9,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="next_step",
            )
        if _contains_any(lower, _EXERCISE_PATTERNS):
            return self._event(
                intent="REQUEST_EXERCISE",
                confidence=0.86,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="exercise_selection",
            )
        if _contains_any(lower, _EXPLANATION_PATTERNS) or "?" in lower:
            return self._event(
                intent="ASK_EXPLANATION",
                confidence=0.78,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="feedback" if phase in {"analysis", "feedback", "next_step"} else None,
            )
        if _contains_any(lower, _OFF_TOPIC_PATTERNS):
            return self._event(
                intent="OFF_TOPIC",
                confidence=0.87,
                source="deterministic_rule",
                phase=phase,
                recommended_transition=None,
            )

        heuristic = self._phase_heuristic(text=text, phase=phase, context=routing_input.recent_conversation_context)
        if heuristic is not None:
            return heuristic

        return self._fallback_classifier(text=text, phase=phase)

    def route_tool_output(
        self,
        *,
        tool_name: str,
        ok: bool,
        result: dict[str, Any] | None,
        error: str | None,
        current_phase: str,
    ) -> RoutedLessonEvent:
        phase = _normalize_phase(current_phase)
        normalized_name = _normalize_text(tool_name).lower()
        payload = result or {}
        if not ok:
            return self._event(
                intent="TOOL_ANALYSIS_FAILED",
                confidence=0.99,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="feedback",
                entities={"tool_name": normalized_name, "error": _normalize_text(error)},
            )
        if normalized_name == "transcribe":
            return self._event(
                intent="TOOL_ANALYSIS_READY",
                confidence=0.99,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="analysis",
                entities={
                    "tool_name": normalized_name,
                    "summary": _normalize_text(str(payload.get("summary", ""))),
                    "confidence": float(payload.get("confidence", 0) or 0),
                },
            )
        if normalized_name in {"lesson_step", "lesson_action"}:
            return self._event(
                intent="REQUEST_EXERCISE",
                confidence=0.84,
                source="phase_heuristic",
                phase=phase,
                recommended_transition="listening",
                entities={"tool_name": normalized_name},
            )
        return self._event(
            intent="OFF_TOPIC",
            confidence=0.5,
            source="fallback_classifier",
            phase=phase,
            recommended_transition=None,
            entities={"tool_name": normalized_name},
        )

    def route_music_phrase_event(
        self,
        *,
        event_type: str,
        current_phase: str,
        payload: dict[str, Any] | None = None,
    ) -> RoutedLessonEvent:
        phase = _normalize_phase(current_phase)
        normalized = _normalize_text(event_type).upper()
        details = payload or {}
        if normalized == "PHRASE_PLAYED":
            return self._event(
                intent="PLAYED_PHRASE",
                confidence=0.95,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="listening",
                entities={"event_type": normalized, "notes": details.get("notes")},
            )
        if normalized == "SILENCE_TIMEOUT":
            return self._event(
                intent="SILENCE_TIMEOUT",
                confidence=0.95,
                source="deterministic_rule",
                phase=phase,
                recommended_transition="next_step",
                entities={"event_type": normalized},
            )
        return self._event(
            intent="OFF_TOPIC",
            confidence=0.45,
            source="fallback_classifier",
            phase=phase,
            recommended_transition=None,
            entities={"event_type": normalized},
        )

    def _phase_heuristic(
        self,
        *,
        text: str,
        phase: str,
        context: tuple[dict[str, Any], ...],
    ) -> RoutedLessonEvent | None:
        del context
        clean = _normalize_text(text)
        if not clean:
            return None

        if phase in {"intro", "goal_capture"}:
            return self._event(
                intent="SHARE_GOAL",
                confidence=0.72,
                source="phase_heuristic",
                phase=phase,
                recommended_transition="exercise_selection",
                entities={"goal_text": clean},
            )
        if phase == "exercise_selection" and len(clean.split()) <= 5:
            return self._event(
                intent="PLAYED_PHRASE",
                confidence=0.63,
                source="phase_heuristic",
                phase=phase,
                recommended_transition="listening",
            )
        if phase in {"feedback", "next_step"} and len(clean.split()) <= 4:
            return self._event(
                intent="READY_FOR_NEXT_STEP",
                confidence=0.61,
                source="phase_heuristic",
                phase=phase,
                recommended_transition="next_step",
            )
        return None

    def _fallback_classifier(self, *, text: str, phase: str) -> RoutedLessonEvent:
        clean = _normalize_text(text)
        if phase in {"feedback", "analysis", "next_step"}:
            return self._event(
                intent="ASK_EXPLANATION",
                confidence=0.52,
                source="fallback_classifier",
                phase=phase,
                recommended_transition="feedback",
            )
        return self._event(
            intent="OFF_TOPIC",
            confidence=0.45,
            source="fallback_classifier",
            phase=phase,
            recommended_transition=None,
            entities={"text": clean[:120]},
        )

    @staticmethod
    def _event(
        *,
        intent: str,
        confidence: float,
        source: str,
        phase: str,
        recommended_transition: str | None,
        entities: dict[str, Any] | None = None,
    ) -> RoutedLessonEvent:
        normalized_intent = intent if intent in INTENT_LABELS else "OFF_TOPIC"
        return RoutedLessonEvent(
            intent=normalized_intent,
            confidence=max(0.0, min(1.0, float(confidence))),
            source=source,
            current_phase=phase,
            recommended_transition=recommended_transition,
            entities=entities or {},
        )
