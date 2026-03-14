from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    collapsed = re.sub(r"\s+", " ", value).strip()
    if not collapsed:
        return None
    return collapsed[:max_length]


class LiveSessionProfile(BaseModel):
    """Validated session metadata for the minimal live backend."""

    mode: Literal["music_tutor", "sight_reading", "technique_practice", "ear_training"] = (
        "music_tutor"
    )
    instrument: str | None = Field(default=None, max_length=80)
    piece: str | None = Field(default=None, max_length=120)
    goal: str | None = Field(default=None, max_length=240)
    camera_expected: bool = False

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, value: str | None) -> str:
        if value is None:
            return "music_tutor"
        normalized = re.sub(r"[\s-]+", "_", str(value).strip().lower())
        return normalized or "music_tutor"

    @field_validator("instrument", mode="before")
    @classmethod
    def normalize_instrument(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=80)

    @field_validator("piece", mode="before")
    @classmethod
    def normalize_piece(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=120)

    @field_validator("goal", mode="before")
    @classmethod
    def normalize_goal(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=240)

    @property
    def label(self) -> str:
        parts = [self.instrument, self.piece, self.goal]
        compact = " · ".join(part for part in parts if part)
        return compact or "General music help"


class LiveSessionProfileResponse(BaseModel):
    session_profile: LiveSessionProfile
    opening_hint: str
    label: str
