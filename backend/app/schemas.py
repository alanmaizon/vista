"""Pydantic models shared across the backend scaffold."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TutorMode(str, Enum):
    guided_reading = "guided_reading"
    morphology_coach = "morphology_coach"
    translation_support = "translation_support"
    oral_reading = "oral_reading"


class ToolDefinition(BaseModel):
    name: str
    description: str
    notes: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    status: Literal["placeholder", "ready"] = "placeholder"


class LiveSessionPlan(BaseModel):
    provider: str = "gemini-live"
    model: str
    websocket_path: str
    audio_input: bool = True
    audio_output: bool = True
    image_input: bool = True
    status: Literal["scaffold"] = "scaffold"
    notes: str


class SessionStateSnapshot(BaseModel):
    session_id: str
    mode: TutorMode
    step: str = "intake"
    target_text: str | None = None
    worksheet_attached: bool = False
    microphone_ready: bool = False
    camera_ready: bool = False
    active_focus: str = "Awaiting the learner's first turn."


class SessionBootstrapRequest(BaseModel):
    learner_name: str = Field(default="Learner", min_length=1, max_length=80)
    mode: TutorMode = TutorMode.guided_reading
    target_text: str | None = Field(default=None, max_length=2000)
    worksheet_attached: bool = False
    microphone_ready: bool = False
    camera_ready: bool = False
    preferred_response_language: str = Field(default="English", min_length=2, max_length=40)


class SessionBootstrapResponse(BaseModel):
    session_id: str
    mode: TutorMode
    mode_label: str
    mode_goal: str
    system_prompt_preview: str
    session_state: SessionStateSnapshot
    tools: list[ToolDefinition] = Field(default_factory=list)
    live_session: LiveSessionPlan
    orchestration: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)


class ModeSummary(BaseModel):
    value: TutorMode
    label: str
    goal: str
    first_turn: str


class RuntimeSnapshot(BaseModel):
    service_name: str
    environment: str
    google_cloud_project: str | None = None
    google_cloud_location: str
    websocket_path: str
    default_mode: TutorMode
    use_google_adk: bool
    google_adk_available: bool
    google_adk_detail: str
    google_genai_available: bool
    google_genai_detail: str
    tools: list[str] = Field(default_factory=list)

