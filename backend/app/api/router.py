"""Top-level API router."""

from __future__ import annotations

from fastapi import APIRouter

from .routes.live import router as live_router
from .routes.runtime import router as runtime_router


api_router = APIRouter(prefix="/api")
api_router.include_router(runtime_router)
api_router.include_router(live_router)

