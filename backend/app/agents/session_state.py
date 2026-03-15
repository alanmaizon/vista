"""Session state scaffold for live tutoring sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from ..schemas import SessionBootstrapRequest, SessionStateSnapshot, TutorMode


@dataclass
class TutorSessionState:
    session_id: str
    learner_name: str
    mode: TutorMode
    target_text: str | None
    worksheet_attached: bool
    microphone_ready: bool
    camera_ready: bool
    step: str = "intake"
    active_focus: str = "Awaiting the learner's first turn."
    transcript: list[str] = field(default_factory=list)

    @classmethod
    def from_request(cls, request: SessionBootstrapRequest) -> "TutorSessionState":
        target_text = request.target_text.strip() if request.target_text else None
        return cls(
            session_id=f"session-{uuid4().hex[:10]}",
            learner_name=request.learner_name,
            mode=request.mode,
            target_text=target_text or None,
            worksheet_attached=request.worksheet_attached,
            microphone_ready=request.microphone_ready,
            camera_ready=request.camera_ready,
        )

    def snapshot(self) -> SessionStateSnapshot:
        return SessionStateSnapshot(
            session_id=self.session_id,
            mode=self.mode,
            step=self.step,
            target_text=self.target_text,
            worksheet_attached=self.worksheet_attached,
            microphone_ready=self.microphone_ready,
            camera_ready=self.camera_ready,
            active_focus=self.active_focus,
        )

