"""Shared dependency helpers for the FastAPI routes."""

from __future__ import annotations

from functools import lru_cache

from ..agents.orchestration.adk_runtime import AncientGreekTutorOrchestrator
from ..settings import get_settings


@lru_cache
def get_orchestrator() -> AncientGreekTutorOrchestrator:
    return AncientGreekTutorOrchestrator(get_settings())

