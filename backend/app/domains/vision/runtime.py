"""Vision domain runtime adapter for Janey Mac."""

from __future__ import annotations

from typing import Any

from ...live.state import LiveSessionState
from ..base import SessionRuntime, VISION_DOMAIN


class VisionRuntime(SessionRuntime):
    """Thin adapter that keeps the existing vision state machine intact."""

    domain = VISION_DOMAIN

    def __init__(self, *, skill: str, goal: str | None = None) -> None:
        self._state = LiveSessionState(skill=skill, goal=goal)

    @property
    def skill(self) -> str:
        return self._state.skill

    @property
    def goal(self) -> str | None:
        return self._state.goal

    @property
    def risk_mode(self) -> str:
        return self._state.risk_mode

    @property
    def completed(self) -> bool:
        return self._state.completed

    def system_prompt(self, vision_prompt: str, music_prompt: str) -> str:
        del music_prompt
        return vision_prompt

    def on_connect_events(self) -> list[dict[str, Any]]:
        return self._state.on_connect_events()

    def opening_prompt(self) -> str:
        return self._state.opening_prompt()

    def on_client_video(self) -> None:
        self._state.on_client_video()

    def on_client_audio(self, audio_bytes: bytes, mime: str | None = None) -> list[dict[str, Any]]:
        del audio_bytes, mime
        return []

    def on_client_confirm(self) -> str | None:
        return self._state.on_client_confirm()

    def on_client_confirm_events(self) -> list[dict[str, Any]]:
        return []

    def on_model_text(self, text: str) -> list[dict[str, Any]]:
        return self._state.on_model_text(text)

    def on_model_audio(self) -> None:
        self._state.on_model_audio()

    def summary_payload(self) -> dict[str, Any]:
        return self._state.summary_payload()
