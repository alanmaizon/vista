"""Shared domain runtime interfaces for the Janey Mac / Eurydice platform."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


VISION_DOMAIN = "VISION"
MUSIC_DOMAIN = "MUSIC"
DEFAULT_DOMAIN = VISION_DOMAIN
SUPPORTED_DOMAINS = {VISION_DOMAIN, MUSIC_DOMAIN}


def normalize_domain(value: str | None) -> str:
    """Normalize a requested domain, defaulting to VISION."""
    normalized = (value or DEFAULT_DOMAIN).strip().upper()
    if normalized in SUPPORTED_DOMAINS:
        return normalized
    return DEFAULT_DOMAIN


@runtime_checkable
class SessionRuntime(Protocol):
    """Minimal interface required by the shared websocket loop."""

    domain: str
    skill: str
    goal: str | None
    risk_mode: str
    completed: bool

    def system_prompt(self, vision_prompt: str, music_prompt: str) -> str:
        """Return the domain-appropriate system prompt for this session."""

    def on_connect_events(self) -> list[dict[str, Any]]:
        """Return any initial status events to emit after the websocket connects."""

    def opening_prompt(self) -> str:
        """Return the first user-facing instruction sent to the model."""

    def on_client_video(self) -> None:
        """Record that the client sent a visual frame."""

    def on_client_confirm(self) -> str | None:
        """Handle a client confirmation message and return a follow-up prompt if needed."""

    def on_model_text(self, text: str) -> list[dict[str, Any]]:
        """Handle model text and optionally emit extra status events."""

    def on_model_audio(self) -> None:
        """Record that the model emitted audio."""

    def summary_payload(self) -> dict[str, Any]:
        """Return a final structured summary for the completed session."""
