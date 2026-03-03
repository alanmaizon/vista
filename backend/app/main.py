"""Eurydice – main FastAPI application entry point."""

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
from .domains import SessionRuntime, build_session_runtime
from .domains.music.api import router as music_router
from .domains.music.render import verovio_runtime_status
from .live.bridge import GeminiLiveBridge, adk_runtime_status
from .live.protocol import CLIENT_AUDIO, CLIENT_CONFIRM, CLIENT_INIT, CLIENT_STOP, CLIENT_VIDEO
from .models import Session
from .sessions import router as sessions_router
from .settings import settings


logger = logging.getLogger("eurydice")
PUBLIC_FIREBASE_WEB_CONFIG_KEYS = {
    "apiKey",
    "authDomain",
    "projectId",
    "storageBucket",
    "messagingSenderId",
    "appId",
    "measurementId",
    "databaseURL",
}

app = FastAPI(title="Eurydice", version="0.3.0")
app.include_router(sessions_router)
app.include_router(music_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ROOT_LOGO = Path(__file__).resolve().parents[2] / "logo.svg"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise Firebase and create the sessions table if needed."""
    init_firebase()
    await init_db()
    adk_available, adk_detail = adk_runtime_status()
    verovio_available, verovio_detail = verovio_runtime_status()
    logger.info(
        "Firebase and database initialised; ADK enabled=%s; ADK importable=%s; ADK detail=%s; Verovio importable=%s; Verovio detail=%s",
        settings.use_adk,
        adk_available,
        adk_detail,
        verovio_available,
        verovio_detail,
    )


@app.get("/")
async def index() -> FileResponse:
    """Serve the Eurydice browser client."""
    return FileResponse(STATIC_DIR / "music.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve the shared logo as the site favicon."""
    return FileResponse(ROOT_LOGO, media_type="image/svg+xml")


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
    filtered = {
        key: value
        for key, value in parsed.items()
        if key in PUBLIC_FIREBASE_WEB_CONFIG_KEYS and isinstance(value, str) and value
    }
    if not filtered:
        logger.warning("Ignoring VISTA_FIREBASE_WEB_CONFIG because no public Firebase web keys were found")
        return {"firebaseConfig": None}
    return {"firebaseConfig": filtered}


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
    runtime: SessionRuntime,
    bridge: GeminiLiveBridge,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            return
        summary = runtime.summary_payload()
        session.summary = summary
        session.risk_mode = runtime.risk_mode
        session.ended_at = datetime.now(timezone.utc)
        session.success = runtime.completed and runtime.risk_mode != "REFUSE"
        session.domain = runtime.domain
        session.mode = runtime.skill
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
    runtime: SessionRuntime,
) -> None:
    async for event in bridge.receive():
        if event.get("type") == "server.audio":
            if not runtime.allow_model_audio():
                continue
            runtime.on_model_audio()
        elif event.get("type") == "server.text":
            text = str(event.get("text", ""))
            extra_events = runtime.on_model_text(text)
            for extra_event in extra_events:
                await ws.send_json(extra_event)
        elif event.get("type") == "server.status":
            event = {
                **event,
                "mode": runtime.risk_mode,
                "skill": runtime.skill,
            }
        await ws.send_json(event)


@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Handle live websocket connections for Eurydice sessions."""
    await ws.accept()

    token = ws.query_params.get("token", "").strip()
    session_id_raw = ws.query_params.get("session_id", "").strip()
    skill = ws.query_params.get("mode", "HEAR_PHRASE").strip().upper() or "HEAR_PHRASE"
    if not token or not session_id_raw:
        try:
            init_message = await ws.receive_json()
        except WebSocketDisconnect:
            return
        except (ValueError, TypeError):
            await ws.send_json({"type": "error", "message": "Malformed websocket init message"})
            await ws.close(code=1008)
            return

        if not isinstance(init_message, dict):
            await ws.send_json({"type": "error", "message": "The first websocket message must be a JSON object"})
            await ws.close(code=1008)
            return

        message_type = str(init_message.get("type", "")).strip()
        if message_type != CLIENT_INIT:
            await ws.send_json({"type": "error", "message": "The first websocket message must be client.init"})
            await ws.close(code=1008)
            return

        token = str(init_message.get("token", "")).strip()
        session_id_raw = str(init_message.get("session_id", "")).strip()
        skill = str(init_message.get("mode", "HEAR_PHRASE")).strip().upper() or "HEAR_PHRASE"
        if not token or not session_id_raw:
            await ws.send_json({"type": "error", "message": "Missing token or session_id in client.init"})
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

    resolved_skill = (session.mode or skill).strip().upper() if getattr(session, "mode", None) else skill
    runtime = build_session_runtime(
        domain=getattr(session, "domain", None),
        skill=resolved_skill,
        goal=session.goal,
    )
    bridge = GeminiLiveBridge(
        model_id=settings.model_id,
        location=settings.location,
        fallback_location=settings.fallback_location,
        project_id=settings.project_id,
        system_prompt=runtime.system_prompt(
            settings.system_instructions,
            settings.music_system_instructions,
        ),
        skill=runtime.skill,
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
                "mode": runtime.risk_mode,
                "skill": runtime.skill,
            }
        )
        for event in runtime.on_connect_events():
            await ws.send_json(event)
        if runtime.uses_model_opening_prompt():
            opening_prompt = runtime.opening_prompt()
            if opening_prompt:
                await bridge.send_text(opening_prompt, role="user")

        forward_task = asyncio.create_task(_forward_bridge_events(ws, bridge, runtime))
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
                    audio_bytes = _decode_b64_payload(message)
                    await bridge.send_audio(audio_bytes)
                    for extra_event in runtime.on_client_audio(audio_bytes, str(message.get("mime", ""))):
                        await ws.send_json(extra_event)
                elif message_type == CLIENT_VIDEO:
                    runtime.on_client_video()
                    await bridge.send_image_jpeg(_decode_b64_payload(message))
                elif message_type == CLIENT_CONFIRM:
                    if "data_b64" in message:
                        audio_bytes = _decode_b64_payload(message)
                        for extra_event in runtime.on_client_audio(audio_bytes, str(message.get("mime", ""))):
                            await ws.send_json(extra_event)
                    confirm_prompt = runtime.on_client_confirm()
                    for extra_event in runtime.on_client_confirm_events():
                        await ws.send_json(extra_event)
                    if confirm_prompt:
                        await bridge.send_text(confirm_prompt, role="user")
                elif message_type == CLIENT_STOP:
                    stop_requested = True
                    await ws.send_json({"type": "server.summary", **runtime.summary_payload()})
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
            await ws.send_json({"type": "server.summary", **runtime.summary_payload()})

        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass
    except Exception as exc:
        logger.exception("Unexpected error in /ws/live: %s", exc)
        await ws.send_json({"type": "error", "message": f"Live session error: {exc}"})
    finally:
        await _persist_session_completion(session_id, runtime=runtime, bridge=bridge)
        await bridge.close()
        with contextlib.suppress(RuntimeError):
            await ws.close()
