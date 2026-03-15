"""Runtime diagnostics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...agents.orchestration.adk_runtime import AncientGreekTutorOrchestrator
from ...schemas import RuntimeSnapshot
from ..dependencies import get_orchestrator


router = APIRouter(tags=["runtime"])


@router.get("/runtime", response_model=RuntimeSnapshot)
def runtime_snapshot(
    orchestrator: AncientGreekTutorOrchestrator = Depends(get_orchestrator),
) -> RuntimeSnapshot:
    return orchestrator.runtime_snapshot()

