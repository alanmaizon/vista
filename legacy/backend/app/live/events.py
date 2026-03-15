"""Normalized server-to-client event contracts for live sessions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LiveEvent(BaseModel):
    """Base model for normalized websocket events."""

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_dump_json(self, **kwargs: Any) -> str:
        return super().model_dump_json(by_alias=True, exclude_unset=True, **kwargs)


class ErrorEvent(LiveEvent):
    type: Literal["error"] = "error"

    @classmethod
    def from_message(cls, message: str) -> "ErrorEvent":
        return cls(payload={"message": message})


class ServerStatusEvent(LiveEvent):
    type: Literal["server.status"] = "server.status"


class ServerTextEvent(LiveEvent):
    type: Literal["server.text"] = "server.text"


class ServerTranscriptEvent(LiveEvent):
    type: Literal["server.transcript"] = "server.transcript"


class ServerAudioEvent(LiveEvent):
    type: Literal["server.audio"] = "server.audio"


class ServerSummaryEvent(LiveEvent):
    type: Literal["server.summary"] = "server.summary"
