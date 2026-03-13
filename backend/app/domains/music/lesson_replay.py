"""Replay harness for guided lesson orchestration regressions.

The harness replays sanitized trace events against ``LessonOrchestrator`` and
produces a compact report used by tests and future CI checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .lesson_orchestrator import LessonDirective, LessonOrchestrator


@dataclass(frozen=True)
class ReplayTrace:
    """Sanitized replay trace consumed by the harness."""

    name: str
    skill: str = "GUIDED_LESSON"
    goal: str | None = None
    events: tuple[dict[str, Any], ...] = ()
    expected_phases: tuple[str, ...] = ()
    expected_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayReport:
    """Replay report for assertions and CI diagnostics."""

    phase_trace: tuple[str, ...]
    transition_signatures: tuple[str, ...]
    action_trace: tuple[str, ...]
    feedback_summaries: tuple[str, ...]
    duplicate_transitions: int
    duplicate_feedback_cards: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_trace": list(self.phase_trace),
            "transition_signatures": list(self.transition_signatures),
            "action_trace": list(self.action_trace),
            "feedback_summaries": list(self.feedback_summaries),
            "duplicate_transitions": self.duplicate_transitions,
            "duplicate_feedback_cards": self.duplicate_feedback_cards,
        }


class LessonReplayHarness:
    """Replays prior traces into the lesson orchestrator."""

    def run_trace(self, trace: ReplayTrace) -> ReplayReport:
        orchestrator = LessonOrchestrator(skill=trace.skill, goal=trace.goal)
        phase_trace: list[str] = []
        transition_signatures: list[str] = []
        action_trace: list[str] = []
        feedback_summaries: list[str] = []
        seen_transition_signatures: set[str] = set()
        seen_feedback_signatures: set[str] = set()
        duplicate_transitions = 0
        duplicate_feedback_cards = 0

        def consume(directive: LessonDirective) -> None:
            nonlocal duplicate_transitions, duplicate_feedback_cards
            for event in directive.events:
                event_type = str(event.get("type", ""))
                if event_type == "server.lesson_state":
                    phase = str(event.get("phase", "")).strip()
                    if phase:
                        phase_trace.append(phase)
                    signature = json.dumps(
                        {
                            "phase": phase,
                            "reason": str(event.get("reason", "")),
                            "status": str(event.get("status", "")),
                            "suggested_actions": list(event.get("suggested_actions", []) or []),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    transition_signatures.append(signature)
                    if signature in seen_transition_signatures:
                        duplicate_transitions += 1
                    else:
                        seen_transition_signatures.add(signature)
                elif event_type == "server.lesson_action":
                    action = str(event.get("action", "")).strip()
                    if action:
                        action_trace.append(action)
                elif event_type == "server.feedback_card":
                    card = event.get("card") if isinstance(event.get("card"), dict) else {}
                    summary = str(card.get("summary", "")).strip()
                    if summary:
                        feedback_summaries.append(summary)
                    signature = json.dumps(card, sort_keys=True, separators=(",", ":"))
                    if signature in seen_feedback_signatures:
                        duplicate_feedback_cards += 1
                    else:
                        seen_feedback_signatures.add(signature)

        consume(orchestrator.start_session())
        for event in trace.events:
            event_type = str(event.get("type", "")).strip().lower()
            if event_type == "transcript_chunk":
                if bool(event.get("partial", False)):
                    continue
                role = str(event.get("role", "")).strip().lower()
                text = str(event.get("text", "")).strip()
                if not text:
                    continue
                if role == "assistant":
                    consume(orchestrator.on_assistant_text(text))
                else:
                    consume(orchestrator.on_user_text(text))
            elif event_type == "user_message":
                consume(orchestrator.on_user_text(str(event.get("text", ""))))
            elif event_type == "assistant_message":
                consume(orchestrator.on_assistant_text(str(event.get("text", ""))))
            elif event_type == "music_phrase_event":
                consume(
                    orchestrator.on_music_phrase_event(
                        event_type=str(event.get("event_name", "PHRASE_PLAYED")),
                        payload=event.get("payload") if isinstance(event.get("payload"), dict) else None,
                    )
                )
            elif event_type == "tool_result":
                consume(
                    orchestrator.on_tool_result(
                        tool_name=str(event.get("tool_name", "")),
                        ok=bool(event.get("ok", False)),
                        result=event.get("result") if isinstance(event.get("result"), dict) else None,
                        error=str(event.get("error", "")) or None,
                    )
                )
            elif event_type == "session_event":
                action = str(event.get("action", "")).strip().lower()
                if action == "stop":
                    consume(orchestrator.on_session_stopped())
                elif action == "start":
                    seen_transition_signatures.clear()
                    seen_feedback_signatures.clear()
                    consume(orchestrator.start_session())

        return ReplayReport(
            phase_trace=tuple(phase_trace),
            transition_signatures=tuple(transition_signatures),
            action_trace=tuple(action_trace),
            feedback_summaries=tuple(feedback_summaries),
            duplicate_transitions=duplicate_transitions,
            duplicate_feedback_cards=duplicate_feedback_cards,
        )


def load_replay_trace(path: str | Path) -> ReplayTrace:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReplayTrace(
        name=str(payload.get("name", "trace")).strip() or "trace",
        skill=str(payload.get("skill", "GUIDED_LESSON")).strip().upper() or "GUIDED_LESSON",
        goal=str(payload.get("goal", "")).strip() or None,
        events=tuple(payload.get("events", []) if isinstance(payload.get("events"), list) else []),
        expected_phases=tuple(payload.get("expected_phases", []) if isinstance(payload.get("expected_phases"), list) else []),
        expected_actions=tuple(payload.get("expected_actions", []) if isinstance(payload.get("expected_actions"), list) else []),
    )
