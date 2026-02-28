"""Pydantic schemas for input and output validation.

These schemas mirror the SQLAlchemy models and are used by FastAPI to
validate and serialize request/response bodies for session creation and
updates.  The `SessionSummary` allows arbitrary structures to be
stored in the summary field using the `Any` type.
"""

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Schema for creating a new session."""

    mode: str = Field(..., description="Skill selected (e.g. NAV_FIND, SHOP_VERIFY)")
    goal: Optional[str] = Field(None, description="Short user-provided goal description")


class SessionUpdate(BaseModel):
    """Schema for updating an existing session."""

    risk_mode: Optional[str] = Field(None, description="Risk mode (NORMAL, CAUTION, REFUSE)")
    ended: Optional[bool] = Field(False, description="Whether to mark the session as ended")
    success: Optional[bool] = Field(None, description="Whether the session completed successfully")
    summary: Optional[Any] = Field(None, description="Structured summary of the session")


class SessionOut(BaseModel):
    """Schema for session retrieval responses."""

    id: uuid.UUID
    mode: str
    risk_mode: str
    goal: Optional[str]
    summary: Optional[Any]

    class Config:
        orm_mode = True