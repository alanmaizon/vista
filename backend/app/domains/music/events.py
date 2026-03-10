"""Normalized server-to-client event contracts for live sessions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LiveEvent(BaseModel):
    """Base model for a normalized server-to-client live event."""

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_dump_json(self, **kwargs: Any) -> str:
        # Override for convenience
        return super().model_dump_json(by_alias=True, exclude_unset=True, **kwargs)


class ErrorEvent(LiveEvent):
    """An error message sent to the client."""

    type: Literal["error"] = "error"

    @classmethod
    def from_message(cls, message: str) -> "ErrorEvent":
        return cls(payload={"message": message})


class ServerStatusEvent(LiveEvent):
    """Connection and agent status update."""

    type: Literal["server.status"] = "server.status"


class ServerTextEvent(LiveEvent):
    """Final assistant text response."""

    type: Literal["server.text"] = "server.text"


class ServerTranscriptEvent(LiveEvent):
    """Partial or final speech transcription."""

    type: Literal["server.transcript"] = "server.transcript"


class ServerAudioEvent(LiveEvent):
    """Assistant audio chunk."""

    type: Literal["server.audio"] = "server.audio"


class ServerToolResultEvent(LiveEvent):
    """Result of a client- or model-invoked tool call."""

    type: Literal["server.tool_result"] = "server.tool_result"


class ServerScoreCaptureEvent(LiveEvent):
    """Result of a successful camera-based score read."""

    type: Literal["server.score_capture"] = "server.score_capture"


class ServerScoreUnclearEvent(LiveEvent):
    """Notification that a camera-based score read was unsuccessful."""

    type: Literal["server.score_unclear"] = "server.score_unclear"


class ServerSummaryEvent(LiveEvent):
    """End-of-session summary."""

    type: Literal["server.summary"] = "server.summary"