"""Main FastAPI application entry point."""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .auth import init_firebase, verify_firebase_token
from .db import AsyncSessionLocal, init_db
from .live.bridge import GeminiLiveBridge, adk_runtime_status
from .live.protocol import CLIENT_AUDIO, CLIENT_CONFIRM, CLIENT_STOP, CLIENT_VIDEO
from .live.state import LiveSessionState
from .models import Session
from .sessions import router as sessions_router
from .settings import settings


logger = logging.getLogger("vista-ai")

app = FastAPI(title="Vista AI Backend", version="0.2.0")
app.include_router(sessions_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise Firebase and create the sessions table if needed."""
    init_firebase()
    await init_db()
    adk_available, adk_detail = adk_runtime_status()
    logger.info(
        "Firebase and database initialised; ADK enabled=%s; ADK importable=%s; detail=%s",
        settings.use_adk,
        adk_available,
        adk_detail,
    )


@app.get("/")
async def index() -> FileResponse:
    """Serve the minimal browser client."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health endpoint to confirm the service is up."""
    return {"status": "ok"}


@app.get("/api/client-config")
async def client_config() -> dict[str, object | None]:
    """Expose non-secret browser config needed by the static client."""
    raw_config = settings.firebase_web_config.strip()
    if not raw_config:
        return {"firebaseConfig": None}
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid VISTA_FIREBASE_WEB_CONFIG JSON")
        return {"firebaseConfig": None}
    if not isinstance(parsed, dict):
        logger.warning("Ignoring non-object VISTA_FIREBASE_WEB_CONFIG payload")
        return {"firebaseConfig": None}
    return {"firebaseConfig": parsed}


async def _load_owned_session(session_id: UUID, user_id: str) -> Session:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorised to access this session")
        return session


async def _update_session_start_metadata(
    session_id: UUID,
    *,
    model_id: str,
    region: str,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            return
        session.model_id = model_id
        session.region = region
        await db.commit()


async def _persist_session_completion(
    session_id: UUID,
    *,
    state: LiveSessionState,
    bridge: GeminiLiveBridge,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            return
        summary = state.summary_payload()
        session.summary = summary
        session.risk_mode = state.risk_mode
        session.ended_at = datetime.now(timezone.utc)
        session.success = state.completed and state.risk_mode != "REFUSE"
        session.model_id = bridge.model_id
        session.region = bridge.active_location
        await db.commit()


def _decode_b64_payload(message: dict, field_name: str = "data_b64") -> bytes:
    data_b64 = message.get(field_name)
    if not isinstance(data_b64, str) or not data_b64:
        raise ValueError(f"Missing {field_name}")
    try:
        return base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid base64 payload in {field_name}") from exc


async def _forward_bridge_events(
    ws: WebSocket,
    bridge: GeminiLiveBridge,
    state: LiveSessionState,
) -> None:
    async for event in bridge.receive():
        if event.get("type") == "server.text":
            text = str(event.get("text", ""))
            extra_events = state.on_model_text(text)
            for extra_event in extra_events:
                await ws.send_json(extra_event)
        elif event.get("type") == "server.status":
            event = {
                **event,
                "mode": state.risk_mode,
                "skill": state.skill,
            }
        await ws.send_json(event)


@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Handle live websocket connections for audio-first Vista sessions."""
    await ws.accept()

    token = ws.query_params.get("token", "").strip()
    session_id_raw = ws.query_params.get("session_id", "").strip()
    skill = ws.query_params.get("mode", "NAV_FIND").strip().upper() or "NAV_FIND"
    if not token or not session_id_raw:
        await ws.send_json({"type": "error", "message": "Missing token or session_id"})
        await ws.close(code=1008)
        return

    try:
        session_id = UUID(session_id_raw)
    except ValueError:
        await ws.send_json({"type": "error", "message": "session_id must be a valid UUID"})
        await ws.close(code=1008)
        return

    try:
        user = await asyncio.to_thread(verify_firebase_token, token)
        session = await _load_owned_session(session_id, user["uid"])
    except HTTPException as exc:
        await ws.send_json({"type": "error", "message": exc.detail})
        await ws.close(code=1008)
        return
    except Exception as exc:
        logger.exception("Failed to validate websocket session: %s", exc)
        await ws.send_json({"type": "error", "message": "Unable to validate the live session"})
        await ws.close(code=1011)
        return

    state = LiveSessionState(skill=skill, goal=session.goal)
    bridge = GeminiLiveBridge(
        model_id=settings.model_id,
        location=settings.location,
        fallback_location=settings.fallback_location,
        project_id=settings.project_id,
        system_prompt=settings.system_instructions,
        skill=state.skill,
        goal=session.goal,
        user_key=user["uid"],
        session_key=str(session_id),
        prefer_adk=settings.use_adk,
    )

    try:
        await bridge.connect()
        logger.info(
            "Live bridge connected for session %s using %s mode",
            session_id,
            "ADK" if bridge.using_adk else "direct Vertex websocket",
        )
        await _update_session_start_metadata(
            session_id,
            model_id=bridge.model_id,
            region=bridge.active_location,
        )
        await ws.send_json(
            {
                "type": "server.status",
                "state": "connected",
                "mode": state.risk_mode,
                "skill": state.skill,
            }
        )
        for event in state.on_connect_events():
            await ws.send_json(event)
        await bridge.send_text(state.opening_prompt(), role="user")

        forward_task = asyncio.create_task(_forward_bridge_events(ws, bridge, state))
        stop_requested = False

        while True:
            try:
                message = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except (ValueError, TypeError):
                await ws.send_json({"type": "error", "message": "Malformed JSON message"})
                continue

            if not isinstance(message, dict):
                await ws.send_json({"type": "error", "message": "Messages must be JSON objects"})
                continue

            message_type = str(message.get("type", "")).strip()
            try:
                if message_type == CLIENT_AUDIO:
                    await bridge.send_audio(_decode_b64_payload(message))
                elif message_type == CLIENT_VIDEO:
                    state.on_client_video()
                    await bridge.send_image_jpeg(_decode_b64_payload(message))
                elif message_type == CLIENT_CONFIRM:
                    confirm_prompt = state.on_client_confirm()
                    if confirm_prompt:
                        await bridge.send_text(confirm_prompt, role="user")
                elif message_type == CLIENT_STOP:
                    stop_requested = True
                    await ws.send_json({"type": "server.summary", **state.summary_payload()})
                    break
                else:
                    await ws.send_json({"type": "error", "message": f"Unsupported message type: {message_type}"})
            except ValueError as exc:
                await ws.send_json({"type": "error", "message": str(exc)})
            except Exception as exc:
                logger.exception("Live websocket message handling failed: %s", exc)
                await ws.send_json({"type": "error", "message": "Failed to process live message"})
                break

        if not stop_requested and ws.client_state.name == "CONNECTED":
            await ws.send_json({"type": "server.summary", **state.summary_payload()})

        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass
    except Exception as exc:
        logger.exception("Unexpected error in /ws/live: %s", exc)
        await ws.send_json({"type": "error", "message": f"Live session error: {exc}"})
    finally:
        await _persist_session_completion(session_id, state=state, bridge=bridge)
        await bridge.close()
        with contextlib.suppress(RuntimeError):
            await ws.close()
