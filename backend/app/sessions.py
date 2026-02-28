"""Session-related REST endpoints for Vista AI.

This router exposes endpoints to create a session when a user begins
interacting with the assistant and to update the session once it
completes.  It uses dependency injection for database sessions and
Firebase authentication.  See `auth.py` for token verification.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth as auth_utils
from .db import get_db
from .models import Session
from .schemas import SessionCreate, SessionUpdate, SessionOut


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut)
async def create_session(
    payload: SessionCreate,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Create a new session entry.

    A session is created at the start of an interaction.  The
    `mode` parameter indicates the selected skill.  The user's
    Firebase UID is used as the foreign key.  Returns the newly
    created session.
    """
    session = Session(
        user_id=current_user["uid"],
        mode=payload.mode,
        risk_mode="NORMAL",
        goal=payload.goal,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut.from_orm(session)


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: uuid.UUID,
    payload: SessionUpdate,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Update an existing session.

    Users may mark a session as ended, update its risk mode,
    indicate success/failure, and/or store a structured summary.  Only
    the owner of the session is allowed to update it.  Throws a
    404 if the session does not exist or a 403 if it does not belong
    to the current user.
    """
    query = select(Session).where(Session.id == session_id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorised to modify this session")
    # Apply updates
    if payload.risk_mode:
        session.risk_mode = payload.risk_mode
    if payload.summary is not None:
        session.summary = payload.summary
    if payload.success is not None:
        session.success = payload.success
    if payload.ended:
        session.ended_at = None  # will be set to current timestamp below
    # Commit changes and set ended_at if necessary
    await db.commit()
    await db.refresh(session)
    return SessionOut.from_orm(session)