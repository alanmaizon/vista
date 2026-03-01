"""Minimal backend state machine for Vista AI live sessions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable


REFUSAL_KEYWORDS = (
    "cross the road",
    "cross a road",
    "cross the street",
    "cross a street",
    "electrical panel",
    "high-voltage",
    "high voltage",
    "breaker box",
)

GOAL_REFUSAL_KEYWORDS = REFUSAL_KEYWORDS + (
    "medication dosing",
    "dosing decision",
    "dosage recommendation",
    "how much should i take",
    "how many should i take",
)

CAUTION_KEYWORDS = (
    "stairs",
    "escalator",
    "traffic",
    "vehicle",
    "car",
    "wet floor",
    "crowd",
    "knife",
    "sharp",
    "hot",
    "boiling",
    "electrical",
)

FRAME_READY_KEYWORDS = (
    "readable",
    "clear enough",
    "clear view",
    "good view",
    "that frame works",
    "i can read it now",
    "i can read the label",
    "i can read the text",
    "i can see it clearly",
    "the frame is clear",
)

FRAME_UNCLEAR_KEYWORDS = (
    "not readable",
    "still not readable",
    "cannot read",
    "can't read",
    "too blurry",
    "blurry",
    "too far",
    "too small",
    "cropped",
    "cut off",
    "blocked",
    "glare",
    "reflection",
    "mirrored",
    "unclear",
)


@dataclass(frozen=True)
class SkillSpec:
    """Runtime metadata for a supported skill."""

    anchor: str
    base_risk: str
    done_when: str
    caution_default: bool = False
    refuse_default: bool = False
    frame_first: bool = False
    handoff: str | None = None
    capture_prompt: str | None = None


DEFAULT_SKILL = "NAV_FIND"

SKILL_SPECS: dict[str, SkillSpec] = {
    "REORIENT": SkillSpec(
        anchor="Provide a one or two sentence scene anchor so the user knows what is ahead, left, and right.",
        base_risk="R0",
        done_when="The user confirms they understand the front, left, and right reference.",
    ),
    "HOLD_STEADY": SkillSpec(
        anchor="Coach the user to hold a steady, readable frame with exact camera instructions.",
        base_risk="R0",
        done_when="You say the frame is readable and the user confirms.",
        frame_first=True,
        capture_prompt=(
            "Start in FRAME mode. Give one exact camera instruction at a time and do not analyze the scene yet. "
            "Only say 'Readable.' when the frame is actually clear and steady."
        ),
    ),
    "FRAME_COACH": SkillSpec(
        anchor="Coach the user to hold a steady, readable frame with exact camera instructions.",
        base_risk="R0",
        done_when="You say the frame is readable and the user confirms.",
        frame_first=True,
        capture_prompt=(
            "Start in FRAME mode. Give one exact camera instruction at a time and do not analyze the scene yet. "
            "Only say 'Readable.' when the frame is actually clear and steady."
        ),
    ),
    "READ_TEXT": SkillSpec(
        anchor="Read exactly what is visible, summarize briefly, and mark uncertain parts.",
        base_risk="R0",
        done_when="The user confirms they received the information they needed.",
        frame_first=True,
        capture_prompt=(
            "Do not read or summarize yet. First require one sign, label, or document section at a time. "
            "Ask the user to move closer until the text fills at least half the frame, center it, reduce glare, "
            "and hold still for two seconds. If any text is blurry, mirrored, cropped, or blocked, say it is "
            "unreadable and ask for one exact camera adjustment."
        ),
    ),
    "NAV_FIND": SkillSpec(
        anchor="Find a door, sign, counter, exit, elevator, or restroom and guide the user there with verification.",
        base_risk="R1",
        done_when="The target is confirmed and the user is positioned at it.",
    ),
    "QUEUE_AND_COUNTER": SkillSpec(
        anchor="Locate the correct queue and service point and align the user safely.",
        base_risk="R1",
        done_when="The user is aligned with the intended queue or counter.",
    ),
    "SHOP_VERIFY": SkillSpec(
        anchor="Verify whether an item matches the requested product, variant, size, and price if visible.",
        base_risk="R1",
        done_when="The user has the correct item or a safe alternative is chosen.",
        frame_first=True,
        capture_prompt=(
            "Do not compare multiple packages at once. Ask for one item front-facing and centered first. "
            "If price matters, ask for the price tag as a separate close frame. If the brand, size, or variant "
            "is not clearly readable, say it is unverified and request a better single-item view."
        ),
    ),
    "PRICE_AND_DEAL_CHECK": SkillSpec(
        anchor="Read prices, unit prices if visible, and compare the relevant items.",
        base_risk="R1",
        done_when="The user selects one item.",
        frame_first=True,
        capture_prompt=(
            "Require one price tag or one item label at a time. Ask for a close, steady view where the price fills "
            "a large part of the frame. Only compare items after each price has been captured clearly."
        ),
    ),
    "MONEY_HANDLING": SkillSpec(
        anchor="Identify notes or coins, confirm change, and help organize cash.",
        base_risk="R1",
        done_when="The user confirms the amount is organized.",
        frame_first=True,
        capture_prompt=(
            "Ask for a plain background and one coin or bank note at a time. Do not estimate from a pile. "
            "If edges, color, or denomination marks are unclear, request a closer single-item view."
        ),
    ),
    "OBJECT_LOCATE": SkillSpec(
        anchor="Locate an item in reachable space and guide the user to it.",
        base_risk="R1",
        done_when="The user confirms they picked it up.",
        frame_first=True,
        capture_prompt=(
            "Start by asking for a slow sweep of one surface or area. Once a likely target appears, ask the user "
            "to stop, center that area, and hold steady. If the scene is cluttered, ask them to narrow the frame "
            "instead of guessing."
        ),
    ),
    "DEVICE_BUTTONS_AND_DIALS": SkillSpec(
        anchor="Identify controls and provide safe, explicit one-step device guidance.",
        base_risk="R1-R2",
        done_when="The requested setting is verified.",
        frame_first=True,
        capture_prompt=(
            "Require one control panel or one dial at a time. Ask for a close frame where labels and indicator marks "
            "are centered and readable before naming any control."
        ),
    ),
    "SOCIAL_CONTEXT": SkillSpec(
        anchor="Describe the nearby social scene without guessing identities or sensitive traits.",
        base_risk="R0-R1",
        done_when="The user confirms they feel socially oriented.",
    ),
    "FACE_TO_SPEAKER": SkillSpec(
        anchor="Orient the user toward the current speaker with directional cues.",
        base_risk="R0",
        done_when="The user is oriented toward the speaker.",
    ),
    "FORM_FILL_HELP": SkillSpec(
        anchor="Guide one form or kiosk step at a time and verify the selected field or button.",
        base_risk="R1",
        done_when="The current form step is completed and confirmed.",
        frame_first=True,
        capture_prompt=(
            "Require a close frame of only the active screen region. Ask the user to center the selected field or "
            "button, reduce glare, and hold steady before you name any control."
        ),
    ),
    "MEDICATION_LABEL_READ": SkillSpec(
        anchor="Read visible medication label text for one item at a time without interpreting dosage or instructions.",
        base_risk="R1",
        done_when="The label text was read clearly, or you explicitly said the label is still unreadable.",
        frame_first=True,
        capture_prompt=(
            "Require exactly one medication item at a time. Ask for the front label first, centered and close enough "
            "that the label fills most of the frame. If text or numbers are mirrored, blurry, cropped, or blocked, "
            "say they are unreadable and ask for a better view instead of guessing."
        ),
    ),
    "COOKING_ASSIST": SkillSpec(
        anchor="MVP scope is cold prep only: read instructions, measure, and identify ingredients.",
        base_risk="R2",
        done_when="The current prep step is completed with verification.",
        caution_default=True,
    ),
    "STAIRS_ESCALATOR_ELEVATOR": SkillSpec(
        anchor="At stairs or escalators, stop first, use conservative guidance, and recommend assistance if uncertain.",
        base_risk="R2",
        done_when="The user reaches a safe decision point.",
        caution_default=True,
    ),
    "TRAFFIC_CROSSING": SkillSpec(
        anchor="Do not guide the user through live traffic.",
        base_risk="R3",
        done_when="You have refused and handed off safely.",
        refuse_default=True,
        handoff="Offer to locate the crossing button or signage, then advise a sighted handoff.",
    ),
    "MEDICATION_DOSING": SkillSpec(
        anchor="Do not make medication dosing decisions.",
        base_risk="R3",
        done_when="You have refused dosing guidance and redirected to MEDICATION_LABEL_READ for label text only.",
        refuse_default=True,
        handoff="Offer MEDICATION_LABEL_READ to read visible label text only, but do not interpret dosage.",
    ),
}


@dataclass
class LiveSessionState:
    """Tracks a single websocket session and emits lightweight guardrails."""

    skill: str
    goal: str | None = None
    phase: str = "INTENT"
    risk_mode: str = "NORMAL"
    awaiting_confirmation: bool = False
    confirmations: int = 0
    saw_video: bool = False
    completed: bool = False
    frame_ready: bool = False
    last_instruction: str | None = None
    last_assistant_text: str | None = None
    saw_assistant_audio: bool = False
    skill_spec: SkillSpec = field(init=False)
    notes: Deque[str] = field(default_factory=lambda: deque(maxlen=8))

    def __post_init__(self) -> None:
        requested_skill = (self.skill or DEFAULT_SKILL).upper()
        self.skill_spec = SKILL_SPECS.get(requested_skill, SKILL_SPECS[DEFAULT_SKILL])
        self.skill = requested_skill if requested_skill in SKILL_SPECS else DEFAULT_SKILL

        if self.skill_spec.refuse_default or self._goal_is_refused():
            self.risk_mode = "REFUSE"
            self.phase = "COMPLETE"
            self.completed = True
            return
        if self.skill_spec.caution_default:
            self.risk_mode = "CAUTION"
        if self.skill_spec.frame_first:
            self.phase = "FRAME"

    def _goal_is_refused(self) -> bool:
        text = (self.goal or "").lower()
        return any(keyword in text for keyword in GOAL_REFUSAL_KEYWORDS)

    def _goal_is_caution(self) -> bool:
        text = (self.goal or "").lower()
        return any(keyword in text for keyword in CAUTION_KEYWORDS)

    def on_connect_events(self) -> list[dict]:
        if self.risk_mode == "REFUSE":
            return [
                {
                    "type": "server.status",
                    "state": "refuse",
                    "mode": self.risk_mode,
                    "skill": self.skill,
                }
            ]
        if self.risk_mode == "CAUTION" or self._goal_is_caution():
            self.risk_mode = "CAUTION"
            return [
                {
                    "type": "server.status",
                    "state": "caution",
                    "mode": self.risk_mode,
                    "skill": self.skill,
                }
            ]
        return []

    def opening_prompt(self) -> str:
        if self.risk_mode == "REFUSE":
            handoff = self.skill_spec.handoff or "Offer a safer alternative."
            return (
                f"The requested task is {self.skill}. This skill is disallowed as an autonomous guide. "
                "Refuse clearly, state the reason briefly, and do not provide operational guidance. "
                f"{handoff}"
            )
        goal_fragment = (
            f"My goal is: {self.goal}. " if self.goal else "Ask one short question to confirm my goal. "
        )
        caution_fragment = (
            "Start in CAUTION mode and use stricter verification before each new step. "
            if self.risk_mode == "CAUTION"
            else ""
        )
        frame_fragment = (
            (
                f"{self.skill_spec.capture_prompt} "
                "Do not analyze, compare, or claim success until you have explicitly confirmed the frame is readable. "
            )
            if self.skill_spec.frame_first and self.skill_spec.capture_prompt
            else ""
        )
        return (
            f"I am starting a {self.skill} session. "
            f"Skill objective: {self.skill_spec.anchor} "
            f"Baseline risk: {self.skill_spec.base_risk}. "
            f"Completion condition: {self.skill_spec.done_when} "
            f"{goal_fragment}"
            f"{caution_fragment}"
            f"{frame_fragment}"
            "Follow the constitution: never guess, ask for a better view when uncertain, "
            "give exactly one instruction at a time, and verify before claiming success."
        )

    def on_client_video(self) -> None:
        self.saw_video = True
        if self._needs_frame_gate():
            self.phase = "FRAME"
        elif self.phase == "INTENT":
            self.phase = "FRAME"

    def on_client_confirm(self) -> str | None:
        if self.risk_mode == "REFUSE":
            return None
        if not self.awaiting_confirmation:
            return None
        if not self.last_instruction and not self.last_assistant_text:
            return None
        self.confirmations += 1
        self.awaiting_confirmation = False
        if self._needs_frame_gate():
            self.phase = "FRAME"
            return (
                "I adjusted the camera. Verify only the frame before you answer the task. "
                "If the view is still unclear, give exactly one camera adjustment. "
                "If it is finally clear enough, say 'Readable.' and then continue carefully."
            )
        if self.phase in {"INTENT", "FRAME", "GUIDE"}:
            self.phase = "VERIFY"
        elif self.phase == "VERIFY":
            self.phase = "GUIDE"
        return (
            "Yes, I finished that step. "
            "Please verify progress before you say it worked, "
            "and then give exactly one next safe step. "
            "If the evidence is unclear, ask for a better view."
        )

    def on_model_text(self, text: str) -> list[dict]:
        clean = " ".join(text.split())
        if not clean:
            return []
        self.last_assistant_text = clean
        self.notes.append(clean)

        events: list[dict] = []
        risk_update = self._update_risk_mode(clean)
        if risk_update:
            events.append(risk_update)

        lower = clean.lower()
        if self.risk_mode != "REFUSE":
            if self._needs_frame_gate():
                if self._frame_is_ready(lower):
                    self.frame_ready = True
                    self.phase = "GUIDE"
                else:
                    self.phase = "FRAME"
                    self.awaiting_confirmation = True
                    self.last_instruction = self._first_sentence(clean)
                    return events

            if any(token in lower for token in ("hold still", "confirming", "let me check", "verify")):
                self.phase = "VERIFY"
            elif any(token in lower for token in ("done", "confirmed", "you reached", "match", "not a match")):
                self.phase = "COMPLETE"
                self.completed = True
            elif self.phase == "INTENT":
                self.phase = "FRAME"
            else:
                self.phase = "GUIDE"

            self.awaiting_confirmation = self.phase in {"FRAME", "GUIDE", "VERIFY"}
            if self.awaiting_confirmation:
                self.last_instruction = self._first_sentence(clean)

        return events

    def on_model_audio(self) -> None:
        self.saw_assistant_audio = True

    def _update_risk_mode(self, text: str) -> dict | None:
        lower = text.lower()
        if self.risk_mode != "REFUSE" and any(keyword in lower for keyword in REFUSAL_KEYWORDS):
            self.risk_mode = "REFUSE"
            self.phase = "COMPLETE"
            self.completed = True
            self.awaiting_confirmation = False
            return {
                "type": "server.status",
                "state": "refuse",
                "mode": self.risk_mode,
                "skill": self.skill,
            }
        if self.risk_mode == "NORMAL" and any(keyword in lower for keyword in CAUTION_KEYWORDS):
            self.risk_mode = "CAUTION"
            return {
                "type": "server.status",
                "state": "caution",
                "mode": self.risk_mode,
                "skill": self.skill,
            }
        return None

    def summary_payload(self) -> dict:
        bullets = [
            f"Skill: {self.skill}. Baseline risk: {self.skill_spec.base_risk}.",
            f"Goal: {self.goal or 'Not explicitly captured in the session metadata.'}",
            (
                f"Risk mode ended in {self.risk_mode}. "
                f"Phase reached: {self.phase}. Confirmations received: {self.confirmations}."
            ),
            (
                "Camera frames were shared during the session."
                if self.saw_video
                else "The session stayed audio-only."
            ),
        ]
        if self.skill_spec.frame_first:
            bullets.append(
                "Frame gate cleared before analysis."
                if self.frame_ready
                else "Frame gate never cleared; the assistant should keep asking for a better view."
            )
        if self.completed:
            bullets.append(f"Done when: {self.skill_spec.done_when}")
        elif self.last_instruction:
            bullets.append(f"Last guided step: {self.last_instruction}")
        elif self.last_assistant_text:
            bullets.append(f"Last assistant response: {self._first_sentence(self.last_assistant_text)}")
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

    def _needs_frame_gate(self) -> bool:
        return self.skill_spec.frame_first and not self.frame_ready and self.risk_mode != "REFUSE"

    @staticmethod
    def _frame_is_ready(lower: str) -> bool:
        if any(token in lower for token in FRAME_UNCLEAR_KEYWORDS):
            return False
        return any(token in lower for token in FRAME_READY_KEYWORDS)

    def recent_notes(self) -> Iterable[str]:
        return tuple(self.notes)
