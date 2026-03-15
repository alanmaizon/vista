"""ADK orchestration scaffold."""

from __future__ import annotations

from typing import Any

from ...live.gemini_live import GeminiLiveGateway
from ...schemas import RuntimeSnapshot, SessionBootstrapRequest, SessionBootstrapResponse
from ...settings import Settings
from ..modes import get_mode_definition, list_mode_summaries
from ..prompts import build_system_prompt, preview_prompt
from ..session_state import TutorSessionState
from ..tools import build_default_tool_registry


def google_adk_status() -> dict[str, Any]:
    try:
        import google.adk  # type: ignore  # noqa: F401
    except ImportError:
        return {"available": False, "detail": "google-adk is not installed yet"}
    return {"available": True, "detail": "google-adk import succeeded"}


class AncientGreekTutorOrchestrator:
    """Small coordinator that keeps future ADK wiring behind one seam."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tool_registry = build_default_tool_registry()
        self._live_gateway = GeminiLiveGateway(settings)

    def mode_summaries(self):
        return list_mode_summaries()

    def bootstrap_session(self, request: SessionBootstrapRequest) -> SessionBootstrapResponse:
        session_state = TutorSessionState.from_request(request)
        mode_definition = get_mode_definition(request.mode)
        system_prompt = build_system_prompt(
            request.mode,
            response_language=request.preferred_response_language,
        )
        live_session = self._live_gateway.build_session_plan(request, system_prompt)

        return SessionBootstrapResponse(
            session_id=session_state.session_id,
            mode=request.mode,
            mode_label=mode_definition.label,
            mode_goal=mode_definition.goal,
            system_prompt_preview=preview_prompt(system_prompt),
            session_state=session_state.snapshot(),
            tools=self._tool_registry.list_definitions(),
            live_session=live_session,
            orchestration={
                "engine": "google-adk",
                "status": "scaffold",
                "adk_ready": google_adk_status()["available"],
                "loop": [
                    "listen to learner input",
                    "ground against target text or worksheet",
                    "decide whether to hint, parse, grade, or drill",
                    "respond with short spoken tutoring guidance",
                ],
            },
            next_steps=[
                "Open the live websocket and exchange a Gemini Live session handshake.",
                "Convert tool placeholders into executable parse, grade, and drill actions.",
                "Persist transcript turns and worksheet metadata outside the in-memory scaffold.",
            ],
        )

    def runtime_snapshot(self) -> RuntimeSnapshot:
        adk = google_adk_status()
        genai = self._live_gateway.sdk_status()
        return RuntimeSnapshot(
            service_name=self._settings.app_name,
            environment=self._settings.environment,
            google_cloud_project=self._settings.google_cloud_project,
            google_cloud_location=self._settings.google_cloud_location,
            websocket_path=self._settings.websocket_path,
            default_mode=self._settings.default_tutoring_mode,
            use_google_adk=self._settings.use_google_adk,
            google_adk_available=bool(adk["available"]),
            google_adk_detail=str(adk["detail"]),
            google_genai_available=bool(genai["available"]),
            google_genai_detail=str(genai["detail"]),
            tools=self._tool_registry.names(),
        )

