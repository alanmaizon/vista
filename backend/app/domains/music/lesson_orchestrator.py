"""Guided lesson orchestration layer for Gemini Live music tutoring.

This module sits above the Live transport and deterministic tools. It tracks
coarse lesson phases and emits structured directives for:
- client UI state updates,
- deterministic lesson actions,
- and short model-facing context updates.
"""

from __future__ import annotations

from collections import deque
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from .lesson_intents import LessonIntentRouter, LessonRoutingInput, RoutedLessonEvent


LessonPhase = Literal[
    "idle",
    "intro",
    "goal_capture",
    "exercise_selection",
    "listening",
    "analysis",
    "feedback",
    "next_step",
    "session_complete",
]


@dataclass
class LessonDirective:
    """Output contract from one orchestration decision step."""

    events: list[dict[str, Any]] = field(default_factory=list)
    model_context_messages: list[str] = field(default_factory=list)


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _action_label(action: str) -> str:
    mapping = {
        "capture_phrase": "Capture phrase",
        "prepare_lesson": "Prepare lesson",
        "next_exercise": "Next exercise",
        "replay_phrase": "Replay phrase",
    }
    return mapping.get(action, action.replace("_", " ").title())


@dataclass
class LessonOrchestrator:
    """State machine for a conversation-first guided lesson flow."""

    skill: str
    goal: str | None = None
    intent_router: LessonIntentRouter = field(default_factory=LessonIntentRouter)
    phase: LessonPhase = "idle"
    captured_goal: str | None = None
    _transition_id: int = 0
    _last_transition_signature: str | None = None
    _last_assistant_text: str = ""
    _last_feedback_summary: str = ""
    _recent_context: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=8))

    def start_session(self) -> LessonDirective:
        directive = LessonDirective()
        base_status = "Welcome. Tell me what you want to work on in this lesson."
        if _normalize_text(self.goal):
            self.captured_goal = _normalize_text(self.goal)
            base_status = f"Welcome back. We can continue with: {self.captured_goal}"
        self._transition(
            directive,
            new_phase="intro",
            reason="session_started",
            status=base_status,
            suggested_actions=("share_goal",),
        )
        return directive

    def on_session_stopped(self) -> LessonDirective:
        directive = LessonDirective()
        self._transition(
            directive,
            new_phase="session_complete",
            reason="session_stopped",
            status="Session complete. Restart when you're ready for the next guided step.",
            suggested_actions=("restart_session",),
        )
        return directive

    def on_assistant_text(self, text: str) -> LessonDirective:
        directive = LessonDirective()
        clean = _normalize_text(text)
        if not clean:
            return directive
        self._last_assistant_text = clean
        self._remember_context("assistant", clean)
        if self.phase == "intro":
            self._transition(
                directive,
                new_phase="goal_capture",
                reason="assistant_greeted",
                status="Great. Share your goal in one sentence so I can select an exercise.",
                suggested_actions=("share_goal",),
            )
        elif self.phase == "feedback":
            self._transition(
                directive,
                new_phase="next_step",
                reason="feedback_delivered",
                status="Nice work. Choose whether to replay this phrase or try the next exercise.",
                suggested_actions=("replay_phrase", "next_exercise"),
            )
        return directive

    def on_user_text(self, text: str) -> LessonDirective:
        directive = LessonDirective()
        clean = _normalize_text(text)
        if not clean:
            return directive
        self._remember_context("user", clean)
        routed_event = self.intent_router.route_user_input(
            LessonRoutingInput(
                latest_user_transcript=clean,
                current_phase=self.phase,
                recent_conversation_context=tuple(self._recent_context),
                deterministic_tool_outputs=None,
                music_phrase_events=(),
                session_metadata={"captured_goal": self.captured_goal or ""},
            )
        )
        directive.model_context_messages.append(
            self._build_model_context_message("lesson_routed_intent", routed_event.as_dict())
        )
        self._apply_routed_user_event(
            directive,
            routed_event=routed_event,
            raw_user_text=clean,
        )
        return directive

    def on_music_phrase_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> LessonDirective:
        directive = LessonDirective()
        routed_event = self.intent_router.route_music_phrase_event(
            event_type=event_type,
            current_phase=self.phase,
            payload=payload,
        )
        directive.model_context_messages.append(
            self._build_model_context_message("lesson_routed_intent", routed_event.as_dict())
        )
        if routed_event.intent == "PLAYED_PHRASE":
            self._transition(
                directive,
                new_phase="listening",
                reason="music_phrase_event",
                status="I heard a phrase event. Capture one clear phrase for deterministic analysis.",
                suggested_actions=("capture_phrase",),
                lesson_action="capture_phrase",
                auto_action=True,
            )
        elif routed_event.intent == "SILENCE_TIMEOUT":
            self._transition(
                directive,
                new_phase="next_step",
                reason="silence_timeout",
                status="No problem. We can continue with one small next step when you're ready.",
                suggested_actions=("next_exercise", "replay_phrase"),
            )
        return directive

    def on_tool_result(
        self,
        *,
        tool_name: str,
        ok: bool,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> LessonDirective:
        directive = LessonDirective()
        normalized_name = _normalize_text(tool_name).lower()
        payload = result or {}
        routed_tool_event = self.intent_router.route_tool_output(
            tool_name=tool_name,
            ok=ok,
            result=payload,
            error=error,
            current_phase=self.phase,
        )
        directive.model_context_messages.append(
            self._build_model_context_message("lesson_routed_intent", routed_tool_event.as_dict())
        )

        if not ok:
            self._transition(
                directive,
                new_phase="feedback",
                reason=f"{normalized_name}_failed",
                status=f"Tool error from {normalized_name}: {_normalize_text(error) or 'unknown error'}.",
                suggested_actions=("replay_phrase", "prepare_lesson"),
            )
            return directive

        if normalized_name == "transcribe":
            self._transition(
                directive,
                new_phase="analysis",
                reason="transcribe_completed",
                status="Analyzing your phrase with deterministic pitch/rhythm evidence.",
                suggested_actions=("review_feedback",),
            )
            summary = _normalize_text(str(payload.get("summary", ""))) or "Phrase analysis is ready."
            confidence = float(payload.get("confidence", 0) or 0)
            notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
            feedback_card = {
                "title": "Phrase feedback",
                "summary": summary,
                "confidence": confidence,
                "notes": [note.get("note_name") for note in notes if isinstance(note, dict) and note.get("note_name")],
            }
            self._last_feedback_summary = summary
            self._transition(
                directive,
                new_phase="feedback",
                reason="deterministic_feedback_ready",
                status=summary,
                suggested_actions=("replay_phrase", "next_exercise") if confidence >= 0.68 else ("replay_phrase",),
                feedback_card=feedback_card,
            )
            directive.model_context_messages.append(
                self._build_model_context_message(
                    "deterministic_phrase_feedback",
                    {
                        "summary": summary,
                        "confidence": confidence,
                        "notes": feedback_card["notes"],
                    },
                )
            )
            return directive

        if normalized_name in {"lesson_action", "lesson_step"}:
            comparison_payload = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else None
            if comparison_payload:
                self._transition(
                    directive,
                    new_phase="analysis",
                    reason=f"{normalized_name}_comparison",
                    status="Comparison complete. Building corrective feedback.",
                    suggested_actions=("review_feedback",),
                )
                summary = _normalize_text(str(comparison_payload.get("summary", ""))) or "Comparison feedback is ready."
                feedback_card = {
                    "title": "Comparison feedback",
                    "summary": summary,
                    "accuracy": comparison_payload.get("accuracy"),
                    "mismatches": comparison_payload.get("mismatches") if isinstance(comparison_payload.get("mismatches"), list) else [],
                }
                self._last_feedback_summary = summary
                self._transition(
                    directive,
                    new_phase="feedback",
                    reason="comparison_feedback_ready",
                    status=summary,
                    suggested_actions=("replay_phrase", "next_exercise"),
                    feedback_card=feedback_card,
                )
                directive.model_context_messages.append(
                    self._build_model_context_message(
                        "deterministic_comparison_feedback",
                        {"summary": summary, "accuracy": comparison_payload.get("accuracy")},
                    )
                )
                return directive
            self._transition(
                directive,
                new_phase="listening",
                reason=f"{normalized_name}_ready",
                status="Exercise selected. Play when ready and I will listen for deterministic feedback.",
                suggested_actions=("capture_phrase",),
            )
            return directive

        return directive

    def _apply_routed_user_event(
        self,
        directive: LessonDirective,
        *,
        routed_event: RoutedLessonEvent,
        raw_user_text: str,
    ) -> None:
        lower = raw_user_text.lower()
        intent = routed_event.intent

        if self.phase == "idle":
            self._transition(
                directive,
                new_phase="intro",
                reason="user_turn_before_intro",
                status="Let's begin. Tell me what you want to work on.",
                suggested_actions=("share_goal",),
            )

        if intent == "STOP_REQUEST":
            self._transition(
                directive,
                new_phase="session_complete",
                reason="session_stopped",
                status="Session complete. Restart when you're ready for the next guided step.",
                suggested_actions=("restart_session",),
            )
            return

        if intent == "SHARE_GOAL" and self.phase in {"intro", "goal_capture"}:
            if self.phase == "intro":
                self._transition(
                    directive,
                    new_phase="goal_capture",
                    reason="goal_capture_requested",
                    status="What specific skill do you want to improve right now?",
                    suggested_actions=("share_goal",),
                )
            self.captured_goal = raw_user_text
            self._transition(
                directive,
                new_phase="exercise_selection",
                reason="goal_captured",
                status=f"Goal captured: {self.captured_goal}. Let's pick a short first exercise.",
                suggested_actions=("prepare_lesson", "capture_phrase"),
            )
            return

        if intent in {"REQUEST_EXERCISE", "READY_FOR_NEXT_STEP"} and self.phase in {
            "feedback",
            "next_step",
            "analysis",
            "exercise_selection",
        }:
            next_reason = "next_step_requested" if intent == "READY_FOR_NEXT_STEP" else "exercise_requested"
            self._transition(
                directive,
                new_phase="next_step" if intent == "READY_FOR_NEXT_STEP" else "exercise_selection",
                reason=next_reason,
                status="Great. Let's choose the next focused step." if intent == "READY_FOR_NEXT_STEP" else "Let's select a short exercise to continue.",
                suggested_actions=("prepare_lesson", "capture_phrase")
                if intent == "REQUEST_EXERCISE"
                else ("next_exercise", "replay_phrase"),
            )
            return

        if intent in {"ASK_FEEDBACK", "PLAYED_PHRASE", "REPEAT_REQUEST"}:
            reason = "repeat_requested" if intent == "REPEAT_REQUEST" else "phrase_check_requested"
            status = (
                "Let's run it one more time. Play one clear phrase and I'll analyze it deterministically."
                if intent == "REPEAT_REQUEST"
                else "Understood. Play one clear phrase now and I'll analyze it deterministically."
            )
            self._transition(
                directive,
                new_phase="listening",
                reason=reason,
                status=status,
                suggested_actions=("capture_phrase",),
                lesson_action="capture_phrase",
                auto_action=intent != "REPEAT_REQUEST",
            )
            return

        if intent in {"CONFUSED_FOLLOWUP", "ASK_EXPLANATION"} and self.phase in {
            "feedback",
            "next_step",
            "exercise_selection",
            "analysis",
            "listening",
        }:
            follow_up_status = (
                "Let's reframe the concept with one simpler step, then we'll try it again."
                if any(token in lower for token in ("struggle", "hard", "confused", "again", "slow"))
                else "Good follow-up. I'll clarify and keep the next step short."
            )
            self._transition(
                directive,
                new_phase="feedback",
                reason="follow_up_question",
                status=follow_up_status,
                suggested_actions=("replay_phrase", "next_exercise"),
            )
            return

        if intent == "SILENCE_TIMEOUT":
            self._transition(
                directive,
                new_phase="next_step",
                reason="silence_timeout",
                status="No problem. Let's continue with one small next step whenever you're ready.",
                suggested_actions=("next_exercise", "replay_phrase"),
            )

    def _remember_context(self, role: str, text: str) -> None:
        clean = _normalize_text(text)
        if not clean:
            return
        self._recent_context.append({"role": role, "text": clean})

    def _transition(
        self,
        directive: LessonDirective,
        *,
        new_phase: LessonPhase,
        reason: str,
        status: str,
        suggested_actions: tuple[str, ...] = (),
        feedback_card: dict[str, Any] | None = None,
        lesson_action: str | None = None,
        auto_action: bool = False,
    ) -> None:
        previous_phase = self.phase
        signature_payload = {
            "phase": new_phase,
            "reason": reason,
            "status": _normalize_text(status),
            "suggested_actions": list(suggested_actions),
            "feedback_summary": _normalize_text(str((feedback_card or {}).get("summary", ""))),
            "lesson_action": lesson_action or "",
        }
        signature = json.dumps(signature_payload, sort_keys=True, separators=(",", ":"))
        if signature == self._last_transition_signature:
            return

        self.phase = new_phase
        self._transition_id += 1
        self._last_transition_signature = signature
        payload: dict[str, Any] = {
            "type": "server.lesson_state",
            "phase": new_phase,
            "previous_phase": previous_phase,
            "reason": reason,
            "status": _normalize_text(status),
            "suggested_actions": list(suggested_actions),
            "transition_id": self._transition_id,
        }
        if self.captured_goal:
            payload["captured_goal"] = self.captured_goal
        if feedback_card:
            payload["feedback_card"] = feedback_card
        directive.events.append(payload)

        if feedback_card:
            directive.events.append(
                {
                    "type": "server.feedback_card",
                    "phase": new_phase,
                    "transition_id": self._transition_id,
                    "card": feedback_card,
                }
            )
        if lesson_action:
            directive.events.append(
                {
                    "type": "server.lesson_action",
                    "phase": new_phase,
                    "transition_id": self._transition_id,
                    "action": lesson_action,
                    "action_label": _action_label(lesson_action),
                    "reason": reason,
                    "auto": auto_action,
                }
            )

        directive.model_context_messages.append(
            self._build_model_context_message(
                "lesson_phase_transition",
                {
                    "phase": new_phase,
                    "reason": reason,
                    "status": _normalize_text(status),
                    "captured_goal": self.captured_goal or "",
                    "last_feedback_summary": self._last_feedback_summary,
                },
            )
        )

    @staticmethod
    def _build_model_context_message(event_kind: str, payload: dict[str, Any]) -> str:
        compact = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        return f'LESSON_CONTEXT: {{"event":"{event_kind}","payload":{compact}}}'
