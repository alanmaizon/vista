"""Music domain runtime scaffold for Eurydice."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from ..base import MUSIC_DOMAIN, SessionRuntime


@dataclass(frozen=True)
class MusicSkillSpec:
    """Runtime metadata for a supported music skill."""

    anchor: str
    done_when: str
    frame_first: bool = False
    capture_prompt: str | None = None


DEFAULT_MUSIC_SKILL = "HEAR_PHRASE"

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
        return []

    def opening_prompt(self) -> str:
        goal_fragment = (
            f"My music goal is: {self.goal}. "
            if self.goal
            else "Ask one short question to confirm the music task. "
        )
        frame_fragment = (
            f"{self.skill_spec.capture_prompt} "
            if self.skill_spec.frame_first and self.skill_spec.capture_prompt
            else ""
        )
        return (
            f"I am starting a {self.skill} music tutoring session. "
            f"Skill objective: {self.skill_spec.anchor} "
            f"Completion condition: {self.skill_spec.done_when} "
            f"{goal_fragment}"
            f"{frame_fragment}"
            "Never guess musical details. If the score view or the performance is unclear, "
            "ask for one narrower replay or one clearer frame before you analyze."
        )

    def on_client_video(self) -> None:
        self.saw_video = True
        if self.skill_spec.frame_first and not self.frame_ready:
            self.phase = "FRAME"

    def on_client_confirm(self) -> str | None:
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

    def on_model_text(self, text: str) -> list[dict[str, str]]:
        clean = " ".join(text.split())
        if not clean:
            return []

        self.last_assistant_text = clean
        self.notes.append(clean)
        self.last_instruction = self._first_sentence(clean)
        lower = clean.lower()

        if self.skill_spec.frame_first and not self.frame_ready:
            if "readable" in lower or "clear" in lower:
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

    @staticmethod
    def _first_sentence(text: str) -> str:
        for separator in (". ", "? ", "! "):
            if separator in text:
                return text.split(separator, 1)[0].strip() + separator.strip()
        return text.strip()
