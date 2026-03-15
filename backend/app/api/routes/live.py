"""Routes related to live tutoring session bootstrap."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...agents.orchestration.adk_runtime import AncientGreekTutorOrchestrator
from ...schemas import ModeSummary, SessionBootstrapRequest, SessionBootstrapResponse
from ..dependencies import get_orchestrator


router = APIRouter(tags=["live"])


@router.get("/live/modes", response_model=list[ModeSummary])
def list_tutoring_modes(
    orchestrator: AncientGreekTutorOrchestrator = Depends(get_orchestrator),
) -> list[ModeSummary]:
    return orchestrator.mode_summaries()


@router.post("/live/session", response_model=SessionBootstrapResponse)
def create_live_session(
    request: SessionBootstrapRequest,
    orchestrator: AncientGreekTutorOrchestrator = Depends(get_orchestrator),
) -> SessionBootstrapResponse:
    return orchestrator.bootstrap_session(request)

