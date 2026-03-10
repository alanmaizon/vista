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
from time import monotonic
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .auth import init_firebase, verify_firebase_session_cookie, verify_firebase_token
from .auth_api import router as auth_router
from .db import AsyncSessionLocal, init_db
from .domains import SessionRuntime, build_session_runtime
from .domains.music.api import router as music_router
from .domains.music.context import build_music_live_context
from .domains.music.live_tools import register_music_tools
from .domains.music.models import MusicLiveToolCall
from .domains.music.render import verovio_runtime_status
from .live.bridge import GeminiLiveBridge, adk_runtime_status
from .live.protocol import (
    CLIENT_AUDIO,
    CLIENT_CONFIRM,
    CLIENT_INIT,
    CLIENT_STOP,
    CLIENT_TEXT,
    CLIENT_TOOL,
    CLIENT_VIDEO,
)
from .live.events import (
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
from .conversation_manager import ConversationManager
from .memory import MemoryService, MemoryType, SessionSummary, VectorStore
from .memory.embeddings import EmbeddingClient
from .prompts import PromptComposer
from .tools import ToolError, tool_registry
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

# Global memory service instance (shared across sessions).
_memory_service = MemoryService(
    embedding_client=EmbeddingClient(),
    vector_store=VectorStore(),
)

app = FastAPI(title="Eurydice", version="0.3.0")
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(music_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ROOT_LOGO = Path(__file__).resolve().parents[2] / "logo.svg"
CONTAINER_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend-dist"
LOCAL_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_DIST = (
    CONTAINER_FRONTEND_DIST
    if CONTAINER_FRONTEND_DIST.is_dir()
    else LOCAL_FRONTEND_DIST
    if LOCAL_FRONTEND_DIST.is_dir()
    else None
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if FRONTEND_DIST is not None and (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")
if FRONTEND_DIST is not None and (FRONTEND_DIST / "features").is_dir():
    app.mount("/features", StaticFiles(directory=FRONTEND_DIST / "features"), name="frontend-features")


def _find_logo_file() -> Path | None:
    """Resolve a logo path from the built frontend first, then the repo root."""
    if FRONTEND_DIST is not None:
        frontend_logo = FRONTEND_DIST / "logo.svg"
        if frontend_logo.is_file():
            return frontend_logo
    if ROOT_LOGO.is_file():
        return ROOT_LOGO
    return None

def _find_frontend_file(file_name: str) -> Path | None:
    if FRONTEND_DIST is None:
        return None
    asset_path = FRONTEND_DIST / file_name
    return asset_path if asset_path.is_file() else None

@app.on_event("startup")
async def startup_event() -> None:
    """Initialise Firebase and create the sessions table if needed."""
    init_firebase()
    await init_db()
    register_music_tools()
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
    if FRONTEND_DIST is not None:
        react_index = FRONTEND_DIST / "index.html"
    else:
        react_index = None
    if react_index is not None and react_index.is_file():
        return FileResponse(react_index)
    return FileResponse(STATIC_DIR / "music.html")


@app.get("/workspace")
async def workspace() -> FileResponse:
    """Serve the main client app entrypoint for authenticated workspace routing."""
    return await index()

@app.get("/marble-pattern.png", include_in_schema=False)
async def marble_pattern() -> FileResponse:
    asset_path = _find_frontend_file("marble-pattern.png")
    if asset_path is None:
        raise HTTPException(status_code=404, detail="marble-pattern.png not found")
    return FileResponse(asset_path, media_type="image/png")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve the shared logo as the site favicon."""
    logo_path = _find_logo_file()
    if logo_path is None:
        raise HTTPException(status_code=404, detail="favicon not found")
    return FileResponse(logo_path, media_type="image/svg+xml")


@app.get("/logo.svg", include_in_schema=False)
async def logo() -> FileResponse:
    """Serve the Eurydice logo for frontend hero and branding assets."""
    logo_path = _find_logo_file()
    if logo_path is None:
        raise HTTPException(status_code=404, detail="logo not found")
    return FileResponse(logo_path, media_type="image/svg+xml")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health endpoint to confirm the service is up."""
    return {"status": "ok"}


@app.get("/api/client-config")
async def client_config() -> dict[str, object | None]:
    """Expose non-secret browser config needed by the browser client."""
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


async def _build_live_context_for_user(
    *,
    user_id: str,
    skill: str,
    goal: str | None,
) -> str:
    if not settings.live_context_enabled:
        return ""
    try:
        async with AsyncSessionLocal() as db:
            return await build_music_live_context(
                db,
                user_id=user_id,
                skill=skill,
                goal=goal,
                attempt_limit=settings.live_context_attempt_limit,
                library_limit=settings.live_context_library_limit,
                max_chars=settings.live_context_max_chars,
            )
    except Exception as exc:
        logger.warning("Failed to build live context packet: %s", exc)
        return ""


async def _build_memory_context_for_user(
    *,
    user_id: str,
    goal: str | None,
) -> str:
    """Retrieve relevant musical memories to enrich the session prompt."""
    query = goal or "music practice session"
    try:
        return await _memory_service.build_memory_context(
            query=query,
            user_id=user_id,
            top_k=3,
            max_chars=1200,
        )
    except Exception as exc:
        logger.warning("Failed to build memory context: %s", exc)
        return ""


async def _store_session_memory_summary(
    *,
    session_id: UUID,
    user_id: str,
    runtime: SessionRuntime,
) -> None:
    """Generate and store a session summary as a musical memory."""
    try:
        summary_payload = runtime.summary_payload()
        summary = SessionSummary(
            session_id=str(session_id),
            user_id=user_id,
            session_skill=runtime.skill,
            raw_summary=json.dumps(summary_payload) if summary_payload else "",
        )
        await _memory_service.store_session_summary(
            session_id=str(session_id),
            user_id=user_id,
            summary=summary,
        )
    except Exception as exc:
        logger.warning("Failed to store session memory summary: %s", exc)


def _tool_result_to_model_text(tool_name: str, payload: dict[str, Any], *, max_chars: int = 2400) -> str:
    compact = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    if len(compact) > max_chars:
        compact = compact[: max_chars - 3] + "..."
    return f'TOOL_RESULT: {{"name":"{tool_name}","result":{compact}}}'


def _tool_error_to_model_text(tool_name: str, message: str) -> str:
    escaped = message.replace('"', "'").strip() or "Tool call failed."
    return f'TOOL_ERROR: {{"name":"{tool_name}","message":"{escaped}"}}'


def _classify_tool_error(message: str, *, status_code: int | None = None, unexpected: bool = False) -> str:
    if unexpected:
        return "INTERNAL"
    if status_code in {401, 403}:
        return "AUTH"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code in {408}:
        return "TIMEOUT"
    if status_code == 429:
        return "RATE_LIMIT"
    if status_code is not None and status_code >= 500:
        return "UPSTREAM"
    if status_code in {400, 422}:
        return "VALIDATION"

    normalized = (message or "").lower()
    if "timed out" in normalized or "timeout" in normalized:
        return "TIMEOUT"
    if "unauthor" in normalized or "forbidden" in normalized or "access" in normalized:
        return "AUTH"
    if "not found" in normalized:
        return "NOT_FOUND"
    if "invalid" in normalized or "required" in normalized or "extra inputs" in normalized:
        return "VALIDATION"
    return "TOOL_ERROR"


async def _execute_live_tool_call(
    *,
    user_id: str,
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        return await tool_registry.run_tool(
            db,
            user_id=user_id,
            tool_name=tool_name,
            args=args,
        )


async def _record_live_tool_call(
    *,
    user_id: str,
    session_id: UUID | None,
    tool_name: str,
    source: str,
    status: str,
    latency_ms: int | None,
    error_kind: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                MusicLiveToolCall(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=(tool_name or "").strip().lower() or "unknown",
                    source=(source or "client").strip().lower() or "client",
                    status=status,
                    latency_ms=latency_ms,
                    error_kind=error_kind,
                    error_message=error_message,
                )
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to record live tool telemetry: %s", exc)


async def _handle_live_tool_call(
    *,
    ws: WebSocket,
    bridge: GeminiLiveBridge,
    conversation_manager: ConversationManager,
    user_id: str,
    session_id: UUID | None,
    tool_name: str,
    args: dict[str, Any],
    source: str,
    call_id: str | None = None,
    send_to_model: bool = True,
) -> None:
    started_at = monotonic()
    try:
        payload = await _execute_live_tool_call(
            user_id=user_id,
            tool_name=tool_name,
            args=args,
        )
        event = ServerToolResultEvent(
            payload={
                "name": tool_name,
                "source": source,
                "ok": True,
                "result": payload,
            },
            metadata={"call_id": call_id} if call_id else {},
        )
        conversation_manager.add_tool_result(name=tool_name, result=payload, call_id=call_id)
        await ws.send_json(event.model_dump(mode="json"))
        if send_to_model:
            await bridge.send_text(_tool_result_to_model_text(tool_name, payload), role="user")
        await _record_live_tool_call(
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            source=source,
            status="SUCCESS",
            latency_ms=int((monotonic() - started_at) * 1000),
            error_kind=None,
        )
    except ToolError as exc:
        event = ServerToolResultEvent(
            payload={
                "name": tool_name,
                "source": source,
                "ok": False,
                "error": str(exc),
            },
            metadata={"call_id": call_id} if call_id else {},
        )
        conversation_manager.add_tool_result(name=tool_name, result=None, error=str(exc), call_id=call_id)
        await ws.send_json(event.model_dump(mode="json"))
        if send_to_model:
            await bridge.send_text(_tool_error_to_model_text(tool_name, str(exc)), role="user")
        error_kind = _classify_tool_error(str(exc), status_code=exc.status_code)
        await _record_live_tool_call(
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            source=source,
            status="ERROR",
            latency_ms=int((monotonic() - started_at) * 1000),
            error_kind=error_kind,
            error_message=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected live tool execution failure (%s): %s", tool_name, exc)
        event = ServerToolResultEvent(
            payload={
                "name": tool_name,
                "source": source,
                "ok": False,
                "error": "Unexpected tool execution failure.",
            },
            metadata={"call_id": call_id} if call_id else {},
        )
        conversation_manager.add_tool_result(
            name=tool_name, result=None, error="Unexpected tool execution failure.", call_id=call_id
        )
        await ws.send_json(event.model_dump(mode="json"))
        if send_to_model:
            await bridge.send_text(
                _tool_error_to_model_text(tool_name, "Unexpected tool execution failure."),
                role="user",
            )
        await _record_live_tool_call(
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            source=source,
            status="ERROR",
            latency_ms=int((monotonic() - started_at) * 1000),
            error_kind=_classify_tool_error("Unexpected tool execution failure.", unexpected=True),
            error_message="Unexpected tool execution failure.",
        )


async def _forward_bridge_events(
    ws: WebSocket,
    bridge: GeminiLiveBridge,
    runtime: SessionRuntime,
    conversation_manager: ConversationManager,
    *,
    user_id: str,
    session_id: UUID,
) -> None:
    async for event in bridge.receive():
        normalized_event: LiveEvent | None = None
        event_type = event.get("type")
        if event_type == "server.audio":
            if not runtime.allow_model_audio():
                continue
            runtime.on_model_audio()
            normalized_event = ServerAudioEvent(payload={k: v for k, v in event.items() if k != "type"})
        elif event_type == "server.text":
            text = str(event.get("text", ""))
            if not event.get("partial"):
                conversation_manager.add_assistant_turn(text)
            extra_events = runtime.on_model_text(text)
            for extra_event in extra_events:
                await ws.send_json(extra_event.model_dump(mode="json"))
            normalized_event = ServerTextEvent(payload={k: v for k, v in event.items() if k != "type"})
        elif event_type == "server.transcript":
            normalized_event = ServerTranscriptEvent(payload={k: v for k, v in event.items() if k != "type"})
        elif event_type == "server.status":
            payload = {k: v for k, v in event.items() if k != "type"}
            payload["mode"] = runtime.risk_mode
            payload["skill"] = runtime.skill
            normalized_event = ServerStatusEvent(payload=payload)
        elif event_type == "server.score_capture":
            normalized_event = ServerScoreCaptureEvent(payload={k: v for k, v in event.items() if k != "type"})
        elif event_type == "server.score_unclear":
            normalized_event = ServerScoreUnclearEvent()
        elif event_type == "server.summary":
            normalized_event = ServerSummaryEvent(payload={k: v for k, v in event.items() if k != "type"})
        elif event_type == "server.tool_call":
            tool_name = str(event.get("name", ""))
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            conversation_manager.add_tool_call(name=tool_name, args=args, call_id=str(event.get("call_id", "")))
            await _handle_live_tool_call(
                ws=ws,
                bridge=bridge,
                conversation_manager=conversation_manager,
                user_id=user_id,
                session_id=session_id,
                tool_name=tool_name,
                args=args,
                source="model",
                call_id=str(event.get("call_id", "")).strip() or None,
                send_to_model=True,
            )
            continue
        if normalized_event:
            await ws.send_json(normalized_event.model_dump(mode="json"))


@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Handle live websocket connections for Eurydice sessions."""
    await ws.accept()

    try:
        init_message = await ws.receive_json()
    except WebSocketDisconnect:
        return
    except (ValueError, TypeError):
        await ws.send_json(ErrorEvent.from_message("Malformed websocket init message").model_dump(mode="json"))
        await ws.close(code=1008)
        return

    if not isinstance(init_message, dict):
        await ws.send_json(ErrorEvent.from_message("The first websocket message must be a JSON object").model_dump(mode="json"))
        await ws.close(code=1008)
        return

    message_type = str(init_message.get("type", "")).strip()
    if message_type != CLIENT_INIT:
        await ws.send_json(ErrorEvent.from_message("The first websocket message must be client.init").model_dump(mode="json"))
        await ws.close(code=1008)
        return

    token = str(init_message.get("token", "")).strip()
    session_id_raw = str(init_message.get("session_id", "")).strip()
    skill = str(init_message.get("mode", "HEAR_PHRASE")).strip().upper() or "HEAR_PHRASE"
    if not session_id_raw:
        await ws.send_json(ErrorEvent.from_message("Missing session_id in client.init").model_dump(mode="json"))
        await ws.close(code=1008)
        return

    try:
        session_id = UUID(session_id_raw)
    except ValueError:
        await ws.send_json(ErrorEvent.from_message("session_id must be a valid UUID").model_dump(mode="json"))
        await ws.close(code=1008)
        return

    try:
        session_cookie = ws.cookies.get(settings.session_cookie_name, "").strip()
        if token:
            user = await asyncio.to_thread(verify_firebase_token, token)
        elif session_cookie:
            user = await asyncio.to_thread(verify_firebase_session_cookie, session_cookie)
        else:
            raise HTTPException(status_code=401, detail="Missing token or auth session cookie")
        session = await _load_owned_session(session_id, user["uid"])
    except HTTPException as exc:
        await ws.send_json(ErrorEvent.from_message(exc.detail).model_dump(mode="json"))
        await ws.close(code=1008)
        return
    except Exception as exc:
        logger.exception("Failed to validate websocket session: %s", exc)
        await ws.send_json(ErrorEvent.from_message("Unable to validate the live session").model_dump(mode="json"))
        await ws.close(code=1011)
        return

    resolved_skill = (session.mode or skill).strip().upper() if getattr(session, "mode", None) else skill
    runtime = build_session_runtime(
        domain=getattr(session, "domain", None),
        skill=resolved_skill,
        goal=session.goal,
    )
    conversation_manager = ConversationManager(session_id=session_id, user_id=user["uid"])

    live_context = await _build_live_context_for_user(
        user_id=user["uid"],
        skill=runtime.skill,
        goal=session.goal,
    )
    memory_context = await _build_memory_context_for_user(
        user_id=user["uid"],
        goal=session.goal,
    )
    composer = PromptComposer(runtime, live_context, memory_context=memory_context)
    system_prompt = composer.get_system_prompt()

    bridge = GeminiLiveBridge(
        model_id=settings.model_id,
        location=settings.location,
        fallback_location=settings.fallback_location,
        project_id=settings.project_id,
        system_prompt=system_prompt,
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
            ServerStatusEvent(
                payload={
                    "state": "connected",
                    "mode": runtime.risk_mode,
                    "skill": runtime.skill,
                }
            ).model_dump(mode="json")
        )
        for event in runtime.on_connect_events():
            await ws.send_json(event.model_dump(mode="json"))
        opening_prompt = composer.get_opening_user_prompt()
        if opening_prompt:
            await bridge.send_text(opening_prompt, role="user")

        forward_task = asyncio.create_task(
            _forward_bridge_events(
                ws,
                bridge,
                runtime,
                conversation_manager,
                user_id=user["uid"],
                session_id=session_id,
            )
        )
        stop_requested = False

        while True:
            try:
                message = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except (ValueError, TypeError):
                await ws.send_json(ErrorEvent.from_message("Malformed JSON message").model_dump(mode="json"))
                continue

            if not isinstance(message, dict):
                await ws.send_json(ErrorEvent.from_message("Messages must be JSON objects").model_dump(mode="json"))
                continue

            message_type = str(message.get("type", "")).strip()
            try:
                if message_type == CLIENT_AUDIO:
                    audio_bytes = _decode_b64_payload(message)
                    await bridge.send_audio(audio_bytes)
                    for extra_event in runtime.on_client_audio(audio_bytes, str(message.get("mime", ""))):
                        await ws.send_json(extra_event.model_dump(mode="json"))
                elif message_type == CLIENT_VIDEO:
                    runtime.on_client_video()
                    await bridge.send_image_jpeg(_decode_b64_payload(message))
                elif message_type == CLIENT_CONFIRM:
                    if "data_b64" in message:
                        audio_bytes = _decode_b64_payload(message)
                        for extra_event in runtime.on_client_audio(audio_bytes, str(message.get("mime", ""))):
                            await ws.send_json(extra_event.model_dump(mode="json"))
                    confirm_prompt = runtime.on_client_confirm()
                    for extra_event in runtime.on_client_confirm_events():
                        await ws.send_json(extra_event.model_dump(mode="json"))
                    if confirm_prompt:
                        await bridge.send_text(confirm_prompt, role="user")
                elif message_type == CLIENT_TOOL:
                    tool_name = str(message.get("name", "")).strip()
                    tool_args = message.get("args") if isinstance(message.get("args"), dict) else {}
                    send_to_model = bool(message.get("send_to_model", False))
                    call_id = str(message.get("call_id", "")).strip() or None
                    conversation_manager.add_tool_call(name=tool_name, args=tool_args, call_id=call_id)
                    await _handle_live_tool_call(
                        ws=ws,
                        bridge=bridge,
                        conversation_manager=conversation_manager,
                        user_id=user["uid"],
                        session_id=session_id,
                        tool_name=tool_name,
                        args=tool_args,
                        source="client",
                        call_id=call_id,
                        send_to_model=send_to_model,
                    )
                elif message_type == CLIENT_TEXT:
                    text = str(message.get("text", "")).strip()
                    if not text:
                        raise ValueError("client.text requires a non-empty text field")
                    conversation_manager.add_user_turn(text)
                    # Store substantive user messages as memories (fire-and-forget).
                    if len(text) > 10:
                        asyncio.create_task(
                            _memory_service.store_memory(
                                user_id=user["uid"],
                                content=text,
                                memory_type=MemoryType.USER_QUESTION,
                                metadata={"session_skill": runtime.skill},
                            )
                        )
                    await bridge.send_text(text, role="user")
                elif message_type == CLIENT_STOP:
                    stop_requested = True
                    await ws.send_json(ServerSummaryEvent(payload=runtime.summary_payload()).model_dump(mode="json"))
                    break
                else:
                    await ws.send_json(ErrorEvent.from_message(f"Unsupported message type: {message_type}").model_dump(mode="json"))
            except ValueError as exc:
                await ws.send_json(ErrorEvent.from_message(str(exc)).model_dump(mode="json"))
            except Exception as exc:
                logger.exception("Live websocket message handling failed: %s", exc)
                await ws.send_json(ErrorEvent.from_message("Failed to process live message").model_dump(mode="json"))
                break

        if not stop_requested and ws.client_state.name == "CONNECTED":
            await ws.send_json(ServerSummaryEvent(payload=runtime.summary_payload()).model_dump(mode="json"))

        forward_task.cancel()
        try:
            await forward_task
        except asyncio.CancelledError:
            pass
    except Exception as exc:
        logger.exception("Unexpected error in /ws/live: %s", exc)
        await ws.send_json(ErrorEvent.from_message(f"Live session error: {exc}").model_dump(mode="json"))
    finally:
        await _persist_session_completion(session_id, runtime=runtime, bridge=bridge)
        await _store_session_memory_summary(
            session_id=session_id,
            user_id=user["uid"],
            runtime=runtime,
        )
        await bridge.close()
        with contextlib.suppress(RuntimeError):
            await ws.close()
