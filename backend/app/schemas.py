import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """Schema for creating a new session."""

    mode: str = Field(..., description="Skill selected (e.g. NAV_FIND, SHOP_VERIFY)")
    goal: Optional[str] = Field(None, description="Short user-provided goal description")


class SessionUpdate(BaseModel):
    """Schema for updating an existing session."""

    risk_mode: Optional[str] = Field(None, description="Risk mode (NORMAL, CAUTION, REFUSE)")
    ended: Optional[bool] = Field(None, description="Whether to mark the session as ended")
    success: Optional[bool] = Field(None, description="Whether the session completed successfully")
    summary: Optional[Any] = Field(None, description="Structured summary of the session")


class SessionOut(BaseModel):
    """Schema for session retrieval responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    mode: str
    risk_mode: str
    goal: Optional[str]
    summary: Optional[Any]
    success: Optional[bool]
    model_id: Optional[str]
    region: Optional[str]
