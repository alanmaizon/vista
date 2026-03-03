"""Domain runtime factory for Eurydice."""

from __future__ import annotations

from .base import DEFAULT_DOMAIN, SessionRuntime, normalize_domain
from .music.runtime import MusicRuntime


def build_session_runtime(
    *,
    domain: str | None,
    skill: str,
    goal: str | None = None,
) -> SessionRuntime:
    """Return the correct domain runtime for the session."""
    return MusicRuntime(skill=skill, goal=goal)


__all__ = ["DEFAULT_DOMAIN", "SessionRuntime", "build_session_runtime", "normalize_domain"]
