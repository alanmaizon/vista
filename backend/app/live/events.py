"""Normalized server-to-client event contracts for live sessions.

Re-exports from the canonical definition in ``domains.music.events``
to support the ``live.events`` import path used by the main application.
"""

from __future__ import annotations

from ..domains.music.events import (  # noqa: F401
    ErrorEvent,
    LiveEvent,
    ServerAudioEvent,
    ServerScoreCaptureEvent,
    ServerScoreUnclearEvent,
    ServerStatusEvent,
    ServerSummaryEvent,
    ServerTextEvent,
    ServerToolResultEvent,
    ServerTranscriptEvent,
)

__all__ = [
    "ErrorEvent",
    "LiveEvent",
    "ServerAudioEvent",
    "ServerScoreCaptureEvent",
    "ServerScoreUnclearEvent",
    "ServerStatusEvent",
    "ServerSummaryEvent",
    "ServerTextEvent",
    "ServerToolResultEvent",
    "ServerTranscriptEvent",
]
