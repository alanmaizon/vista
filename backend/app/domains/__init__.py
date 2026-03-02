"""Domain runtime factory for the Janey Mac / Eurydice platform."""

from __future__ import annotations

from .base import DEFAULT_DOMAIN, SessionRuntime, normalize_domain
from .music.runtime import MusicRuntime
from .vision.runtime import VisionRuntime


def build_session_runtime(
    *,
    domain: str | None,
    skill: str,
    goal: str | None = None,
) -> SessionRuntime:
    """Return the correct domain runtime for the session."""
    normalized_domain = normalize_domain(domain)
    if normalized_domain == "MUSIC":
        return MusicRuntime(skill=skill, goal=goal)
    return VisionRuntime(skill=skill, goal=goal)


__all__ = ["DEFAULT_DOMAIN", "SessionRuntime", "build_session_runtime", "normalize_domain"]
