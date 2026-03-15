"""Gemini Live integration planning layer."""

from __future__ import annotations

from typing import Any

from ..schemas import LiveSessionPlan, SessionBootstrapRequest
from ..settings import Settings


class GeminiLiveGateway:
    """A thin seam where the real Gemini Live transport can be added later."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @staticmethod
    def sdk_status() -> dict[str, Any]:
        try:
            import google.genai  # type: ignore  # noqa: F401
        except ImportError:
            return {"available": False, "detail": "google-genai is not installed yet"}
        return {"available": True, "detail": "google-genai import succeeded"}

    def build_session_plan(
        self,
        request: SessionBootstrapRequest,
        system_prompt: str,
    ) -> LiveSessionPlan:
        media_summary = []
        if request.microphone_ready:
            media_summary.append("microphone")
        if request.camera_ready or request.worksheet_attached:
            media_summary.append("visual input")

        notes = (
            "Scaffold only. Next step: replace the placeholder websocket with a real Gemini Live "
            "session bridge and feed it the prompt, media streams, and tool registry."
        )
        if media_summary:
            notes = f"{notes} Prepared media: {', '.join(media_summary)}."

        return LiveSessionPlan(
            model=self._settings.gemini_live_model,
            websocket_path=self._settings.websocket_path,
            notes=notes,
        )

