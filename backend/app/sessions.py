import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth as auth_utils
from .db import get_db
from .models import Session
from .schemas import SessionCreate, SessionUpdate, SessionOut


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _get_owned_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: str,
) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorised to access this session")
    return session


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
    return SessionOut.model_validate(session)


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    """List sessions for the authenticated user."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == current_user["uid"])
        .order_by(Session.started_at.desc())
    )
    sessions = result.scalars().all()
    return [SessionOut.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Fetch one session by id for the authenticated user."""
    session = await _get_owned_session(db, session_id, current_user["uid"])
    return SessionOut.model_validate(session)


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
    session = await _get_owned_session(db, session_id, current_user["uid"])
    # Apply updates
    if payload.risk_mode:
        session.risk_mode = payload.risk_mode
    if payload.summary is not None:
        session.summary = payload.summary
    if payload.success is not None:
        session.success = payload.success
    if payload.ended is True:
        session.ended_at = datetime.now(timezone.utc)
    elif payload.ended is False:
        session.ended_at = None
    await db.commit()
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: dict = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete one session owned by the authenticated user."""
    await _get_owned_session(db, session_id, current_user["uid"])
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
