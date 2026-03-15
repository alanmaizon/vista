"""Music domain runtime scaffold for Eurydice."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from ..base import MUSIC_DOMAIN, SessionRuntime
from ...live.events import (
    LiveEvent,
)
from .transcription import MusicTranscriptionError, transcribe_pcm16


@dataclass(frozen=True)
class MusicSkillSpec:
    """Runtime metadata for a supported music skill."""

    anchor: str
    done_when: str
    frame_first: bool = False
    capture_prompt: str | None = None


DEFAULT_MUSIC_SKILL = "HEAR_PHRASE"
LIVE_HEAR_PHRASE_MAX_BYTES = 16000 * 2 * 6
LIVE_HEAR_PHRASE_MIN_BYTES = 16000

MUSIC_SKILLS: dict[str, MusicSkillSpec] = {
    "SHEET_FRAME_COACH": MusicSkillSpec(
        anchor="Coach the user to frame one staff, one system, or one short score excerpt clearly.",
        done_when="The visible score region is readable and the user confirms the framing is good.",
        frame_first=True,
        capture_prompt=(
            "Ask for one staff line or one short score excerpt at a time. "
            "Center it, reduce glare, and do not read the notation until the frame is clearly readable."
        ),
    ),
    "READ_SCORE": MusicSkillSpec(
        anchor="Read visible music notation and describe it one small region at a time.",
        done_when="The visible measure group was described clearly or you explicitly said the notation is still unclear.",
        frame_first=True,
        capture_prompt=(
            "Ask for one short measure group or one staff line at a time. "
            "Do not identify notes until the notation is centered, close, and readable."
        ),
    ),
    "HEAR_PHRASE": MusicSkillSpec(
        anchor="Identify a melody, interval, chord, or arpeggio and state confidence explicitly.",
        done_when="The musical phrase was identified clearly, or the user was asked for a narrower replay.",
    ),
    "GUIDED_LESSON": MusicSkillSpec(
        anchor="Guide one prepared bar at a time, compare the take, and advance or replay deliberately.",
        done_when="The current prepared bar was confirmed or replay guidance was given before moving on.",
    ),
    "COMPARE_PERFORMANCE": MusicSkillSpec(
        anchor="Compare a played phrase to the intended notes or rhythm and explain the mismatch clearly.",
        done_when="The user understands the main difference and has one next correction to try.",
    ),
    "EAR_TRAIN": MusicSkillSpec(
        anchor="Run one listening drill at a time and verify the answer before continuing.",
        done_when="The current drill answer was verified and the next step was offered.",
    ),
    "GENERATE_EXAMPLE": MusicSkillSpec(
        anchor="Offer an original musical example, clearly labeled as generated, for practice or explanation.",
        done_when="One generated example was proposed and described clearly.",
    ),
}


@dataclass
class MusicRuntime(SessionRuntime):
    """Minimal domain runtime for Eurydice until full music engines are added."""

    skill: str
    goal: str | None = None
    domain: str = MUSIC_DOMAIN
    phase: str = "INTENT"
    risk_mode: str = "NORMAL"
    awaiting_confirmation: bool = False
    confirmations: int = 0
    completed: bool = False
    saw_video: bool = False
    saw_assistant_audio: bool = False
    frame_ready: bool = False
    last_instruction: str | None = None
    last_assistant_text: str | None = None
    notes: Deque[str] = field(default_factory=lambda: deque(maxlen=8))
    recent_audio_bytes: bytearray = field(default_factory=bytearray)
    pending_client_events: Deque[LiveEvent] = field(default_factory=deque)
    read_score_buffer: str = ""
    skill_spec: MusicSkillSpec = field(init=False)

    def __post_init__(self) -> None:
        requested_skill = (self.skill or DEFAULT_MUSIC_SKILL).upper()
        self.skill_spec = MUSIC_SKILLS.get(requested_skill, MUSIC_SKILLS[DEFAULT_MUSIC_SKILL])
        self.skill = requested_skill if requested_skill in MUSIC_SKILLS else DEFAULT_MUSIC_SKILL
        if self.skill_spec.frame_first:
            self.phase = "FRAME"

    def system_prompt(self, vision_prompt: str, music_prompt: str) -> str:
        del vision_prompt
        return music_prompt

    def on_connect_events(self) -> list[dict[str, str]]:
        if self.skill == "HEAR_PHRASE":
            return [
                {
                    "type": "server.text",
                    "text": (
                        "Play one clear phrase, then use Capture phrase. "
                        "The deterministic phrase analyser will handle the result."
                    ),
                }
            ]
        if self.skill == "GUIDED_LESSON":
            return [
                {
                    "type": "server.text",
                    "text": (
                        "Guided mode is text-first: lesson flow is driven by the score and deterministic comparison results."
                    ),
                }
            ]
        if self.skill == "COMPARE_PERFORMANCE":
            return [
                {
                    "type": "server.text",
                    "text": (
                        "Prepare the target notes first, then compare one take at a time. "
                        "The comparison result is authoritative."
                    ),
                }
            ]
        if self.skill in {"READ_SCORE", "SHEET_FRAME_COACH"}:
            return [
                {
                    "type": "server.text",
                    "text": (
                        "Show one short bar clearly. Eurydice will stay text-first while it reads or reframes the score."
                    ),
                }
            ]
        return []

    def uses_model_opening_prompt(self) -> bool:
        return self.skill in {
            "READ_SCORE",
            "SHEET_FRAME_COACH",
            "EAR_TRAIN",
            "GENERATE_EXAMPLE",
        }

    def opening_prompt(self) -> str:
        session_intro = f"I am starting a {self.skill} music tutoring session."
        goal_fragment = (
            f"My music goal is: {self.goal}. Please greet me and let's get started."
            if self.goal
            else "Please greet me and ask what I'd like to work on today."
        )
        return f"{session_intro} {goal_fragment}"

    def skill_instructions(self) -> str:
        """Return skill-specific instructions for the system prompt."""
        frame_fragment = (
            f"{self.skill_spec.capture_prompt}"
            if self.skill_spec.frame_first and self.skill_spec.capture_prompt
            else ""
        )
        live_phrase_fragment = (
            "For HEAR_PHRASE, do not guess interval, chord, or arpeggio identities from the raw live stream alone. "
            "Wait for the user to confirm the replay, then keep your verbal response brief because a server-side phrase analysis may follow."
            if self.skill == "HEAR_PHRASE"
            else ""
        )
        guided_lesson_fragment = (
            "For GUIDED_LESSON, greet the user first, ask one short question about what they want to practice, "
            "and keep the exchange conversational. Follow the lesson phases signaled by LESSON_CONTEXT updates "
            "(intro, goal_capture, exercise_selection, listening, analysis, feedback, next_step). "
            "When the user plays music, wait for deterministic analysis before claiming correctness. "
            "If deterministic comparison or score tools are available, reference them briefly instead of overwhelming the user with controls."
            if self.skill == "GUIDED_LESSON"
            else ""
        )
        read_score_fragment = (
            "For READ_SCORE, once one short bar is clearly readable, give a short musical description and, when you are confident, "
            "include a second sentence that starts exactly with NOTE_LINE: followed by a simple token sequence like C4/q D4/q E4/h. "
            "If the score is still unclear, say SCORE_UNCLEAR and request a tighter frame instead of inventing notes."
            if self.skill == "READ_SCORE"
            else ""
        )
        return (
            f"Current music skill: {self.skill}. "
            f"Skill objective: {self.skill_spec.anchor} "
            f"Completion condition: {self.skill_spec.done_when}. "
            f"{frame_fragment} {live_phrase_fragment} {guided_lesson_fragment} {read_score_fragment} "
            "Never guess musical details. If the score view or the performance is unclear, "
            "ask for one narrower replay or one clearer frame before you analyze."
        ).strip()

    def on_client_video(self) -> None:
        self.saw_video = True
        if self.skill_spec.frame_first and not self.frame_ready:
            self.phase = "FRAME"

    def on_client_audio(self, audio_bytes: bytes, mime: str | None = None) -> list[LiveEvent]:
        del mime
        if not audio_bytes:
            return []
        self.recent_audio_bytes.extend(audio_bytes)
        if len(self.recent_audio_bytes) > LIVE_HEAR_PHRASE_MAX_BYTES:
            overflow = len(self.recent_audio_bytes) - LIVE_HEAR_PHRASE_MAX_BYTES
            del self.recent_audio_bytes[:overflow]
        return []

    def on_client_confirm(self) -> str | None:
        if self.skill == "HEAR_PHRASE":
            self.awaiting_confirmation = False
            self.pending_client_events.extend(self._build_hear_phrase_events())
            return None
        if not self.awaiting_confirmation:
            return None
        self.confirmations += 1
        self.awaiting_confirmation = False
        if self.skill_spec.frame_first and not self.frame_ready:
            self.phase = "FRAME"
            return (
                "I adjusted the score view. Verify only whether the notation is readable yet. "
                "If it is still unclear, give one framing change. If it is clear, say exactly that and continue."
            )
        if self.phase in {"INTENT", "FRAME", "GUIDE"}:
            self.phase = "VERIFY"
        elif self.phase == "VERIFY":
            self.phase = "GUIDE"
        return (
            "Yes, I tried that. Verify the musical result before moving on, "
            "then give exactly one next correction or one next exercise."
        )

    def on_client_confirm_events(self) -> list[LiveEvent]:
        if not self.pending_client_events:
            return []
        events = list(self.pending_client_events)
        self.pending_client_events.clear()
        return events

    def on_model_text(self, text: str) -> list[LiveEvent]:
        clean = " ".join(text.split())
        if not clean:
            return []

        self.last_assistant_text = clean
        self.notes.append(clean)
        self.last_instruction = self._first_sentence(clean)
        lower = clean.lower()

        if self.skill == "READ_SCORE":
            structured_events = self._handle_read_score_text(clean)
            if structured_events:
                return structured_events

        if self.skill_spec.frame_first and not self.frame_ready:
            if "unclear" not in lower and ("readable" in lower or "clear" in lower):
                self.frame_ready = True
                self.phase = "GUIDE"
            else:
                self.phase = "FRAME"
                self.awaiting_confirmation = True
                return []

        if any(token in lower for token in ("done", "complete", "confirmed", "correct")):
            self.phase = "COMPLETE"
            self.completed = True
            self.awaiting_confirmation = False
            return []

        if any(token in lower for token in ("verify", "check again", "play it again")):
            self.phase = "VERIFY"
        else:
            self.phase = "GUIDE"

        self.awaiting_confirmation = True
        return []

    def on_model_audio(self) -> None:
        self.saw_assistant_audio = True

    def allow_model_audio(self) -> bool:
        return self.skill in {"GUIDED_LESSON", "EAR_TRAIN", "GENERATE_EXAMPLE"}

    def summary_payload(self) -> dict[str, list[str]]:
        bullets = [
            f"Domain: {self.domain}. Skill: {self.skill}.",
            f"Goal: {self.goal or 'Not explicitly captured in the session metadata.'}",
            f"Phase reached: {self.phase}. Confirmations received: {self.confirmations}.",
            (
                "Score or visual frames were shared during the session."
                if self.saw_video
                else "The session stayed audio-only."
            ),
        ]
        if self.skill_spec.frame_first:
            bullets.append(
                "The score frame was confirmed readable before analysis."
                if self.frame_ready
                else "The score frame never cleared verification; the tutor should keep requesting a better view."
            )
        if self.completed:
            bullets.append(f"Done when: {self.skill_spec.done_when}")
        elif self.last_instruction:
            bullets.append(f"Last guided step: {self.last_instruction}")
        elif self.saw_assistant_audio:
            bullets.append("Assistant audio was received, but no transcript text was captured.")
        else:
            bullets.append("No assistant response was captured.")
        return {"bullets": bullets[:6]}

    def _expected_phrase_kind(self) -> str:
        goal_lower = (self.goal or "").lower()
        if "arpeggio" in goal_lower:
            return "ARPEGGIO"
        if "chord" in goal_lower:
            return "CHORD"
        if "interval" in goal_lower:
            return "INTERVAL"
        if "melody" in goal_lower:
            return "PHRASE"
        return "AUTO"

    def _handle_read_score_text(self, text: str) -> list[LiveEvent]:
        self.read_score_buffer = f"{self.read_score_buffer} {text}".strip()
        upper_buffer = self.read_score_buffer.upper()
        note_line = self._parse_buffered_note_line()
        if note_line:
            self.read_score_buffer = ""
            self.frame_ready = True
            self.phase = "GUIDE"
            self.awaiting_confirmation = True
            return [{"type": "server.score_capture", "note_line": note_line}]
        if "SCORE_UNCLEAR" in upper_buffer:
            self.read_score_buffer = ""
            self.frame_ready = False
            self.phase = "FRAME"
            self.awaiting_confirmation = True
            return [{"type": "server.score_unclear"}]
        return []

    def _parse_buffered_note_line(self) -> str | None:
        marker = "NOTE_LINE:"
        upper_buffer = self.read_score_buffer.upper()
        marker_index = upper_buffer.find(marker)
        if marker_index < 0:
            return None
        note_line = self.read_score_buffer[marker_index + len(marker) :].strip()
        return note_line or None

    def _build_hear_phrase_events(self) -> list[LiveEvent]:
        clip = bytes(self.recent_audio_bytes)
        self.recent_audio_bytes.clear()
        self.confirmations += 1
        if len(clip) < LIVE_HEAR_PHRASE_MIN_BYTES:
            self.phase = "VERIFY"
            self.completed = False
            return [
                {
                    "type": "server.text",
                    "text": (
                        "I need one clear replay of the phrase before I can analyse it. "
                        "Play the full phrase once, then press confirm again."
                    ),
                }
            ]

        expected = self._expected_phrase_kind()
        try:
            phrase = transcribe_pcm16(clip, sample_rate=16000, expected=expected, max_notes=8)
        except MusicTranscriptionError as exc:
            self.phase = "VERIFY"
            self.completed = False
            return [{"type": "server.text", "text": str(exc)}]

        analysis = self._format_live_phrase_analysis(phrase, expected)
        needs_replay = phrase.confidence < 0.68 or not phrase.notes
        self.phase = "VERIFY" if needs_replay else "COMPLETE"
        self.completed = not needs_replay
        return [{"type": "server.text", "text": analysis}]

    def _format_live_phrase_analysis(self, phrase, expected: str) -> str:
        if not phrase.notes:
            return (
                "I could not confirm a stable pitched phrase from that replay. "
                "Play it again more slowly, one note at a time if needed."
            )

        note_names = ", ".join(note.note_name for note in phrase.notes)
        parts = [f"I heard {len(phrase.notes)} notes: {note_names}."]

        harmony_text = phrase.harmony_hint or ""
        normalized_harmony = harmony_text.replace("Likely ", "").replace(" harmony.", "").strip()
        if expected == "ARPEGGIO" and normalized_harmony:
            parts.append(f"This sounds like an arpeggio outlining {normalized_harmony}.")
        elif harmony_text:
            parts.append(harmony_text)
        elif phrase.interval_hint:
            parts.append(phrase.interval_hint)

        if phrase.confidence < 0.68:
            parts.append("Confidence is still low, so replay it once more for a tighter confirmation.")
        elif phrase.warnings:
            parts.append(phrase.warnings[0])
        else:
            parts.append(f"Confidence {round(phrase.confidence * 100)}%.")

        return " ".join(part for part in parts if part)

    @staticmethod
    def _first_sentence(text: str) -> str:
        for separator in (". ", "? ", "! "):
            if separator in text:
                return text.split(separator, 1)[0].strip() + separator.strip()
        return text.strip()
