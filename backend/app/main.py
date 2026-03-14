"""Minimal FastAPI backend for Eurydice Live."""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .live.bridge import GeminiLiveBridge, adk_runtime_status
from .live.events import ErrorEvent, LiveEvent, ServerStatusEvent, ServerSummaryEvent
from .live.protocol import (
    CLIENT_AUDIO,
    CLIENT_AUDIO_END,
    CLIENT_INIT,
    CLIENT_STOP,
    CLIENT_TEXT,
    CLIENT_VIDEO,
)
from .live_agent import (
    LiveRuntimeRegistry,
    LiveSessionProfile,
    LiveSessionProfileResponse,
    build_opening_user_prompt,
    build_system_prompt,
)
from .settings import settings


logger = logging.getLogger("eurydice.live")
runtime_registry = LiveRuntimeRegistry()
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    adk_available, adk_detail = adk_runtime_status()
    logger.info(
        "Starting Eurydice Live backend; model=%s location=%s fallback=%s use_adk=%s adk_available=%s adk_detail=%s",
        settings.model_id,
        settings.location,
        settings.fallback_location,
        settings.use_adk,
        adk_available,
        adk_detail,
    )
    yield


app = FastAPI(title="Eurydice Live", version="1.0.0", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "eurydice-live",
        "status": "ok",
        "ws_path": "/ws/live",
        "docs_path": "/docs",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/client-config")
async def client_config() -> dict[str, object | None]:
    raw_config = settings.firebase_web_config.strip()
    if not raw_config:
        return {"firebaseConfig": None}
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid VISTA_FIREBASE_WEB_CONFIG JSON")
        return {"firebaseConfig": None}
    if not isinstance(parsed, dict):
        return {"firebaseConfig": None}
    filtered = {
        key: value
        for key, value in parsed.items()
        if key in PUBLIC_FIREBASE_WEB_CONFIG_KEYS and isinstance(value, str) and value
    }
    return {"firebaseConfig": filtered or None}


@app.get("/api/runtime")
async def runtime_info() -> dict[str, Any]:
    adk_available, adk_detail = adk_runtime_status()
    diagnostics = runtime_registry.snapshot()
    return {
        "service": "eurydice-live",
        "model_id": settings.model_id,
        "location": settings.location,
        "fallback_location": settings.fallback_location,
        "project_id": settings.project_id,
        "use_adk": settings.use_adk,
        "adk_available": adk_available,
        "adk_detail": adk_detail,
        "active_session_count": diagnostics["active_session_count"],
        "accepted_client_messages": [
            CLIENT_INIT,
            CLIENT_AUDIO,
            CLIENT_AUDIO_END,
            CLIENT_VIDEO,
            CLIENT_TEXT,
            CLIENT_STOP,
        ],
        "emitted_server_messages": [
            "server.status",
            "server.audio",
            "server.transcript",
            "server.text",
            "server.summary",
            "error",
        ],
    }


@app.get("/api/runtime/debug")
async def runtime_debug() -> dict[str, Any]:
    adk_available, adk_detail = adk_runtime_status()
    return {
        "service": "eurydice-live",
        "model_id": settings.model_id,
        "location": settings.location,
        "fallback_location": settings.fallback_location,
        "project_id": settings.project_id,
        "use_adk": settings.use_adk,
        "adk_available": adk_available,
        "adk_detail": adk_detail,
        **runtime_registry.snapshot(),
    }


@app.post("/api/live/session-profile", response_model=LiveSessionProfileResponse)
async def build_session_profile(profile: LiveSessionProfile) -> LiveSessionProfileResponse:
    return LiveSessionProfileResponse(
        session_profile=profile,
        opening_hint=build_opening_user_prompt(profile),
        label=profile.label,
    )


def _flatten_live_event_envelope(event: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {"type": str(event.get("type", ""))}
    payload = event.get("payload")
    if isinstance(payload, dict):
        flattened.update(payload)
    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        flattened.update(metadata)
    for key, value in event.items():
        if key in {"type", "payload", "metadata"}:
            continue
        if key not in flattened:
            flattened[key] = value
    return flattened


def _live_event_to_wire(event: LiveEvent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, LiveEvent):
        return _flatten_live_event_envelope(event.model_dump(mode="json"))
    if isinstance(event, dict):
        if "payload" in event or "metadata" in event:
            return _flatten_live_event_envelope(event)
        return event
    return {"type": "error", "message": "Invalid live event payload."}


async def _send_live_event(ws: WebSocket, event: LiveEvent | dict[str, Any]) -> None:
    await ws.send_json(_live_event_to_wire(event))


def _decode_b64_payload(message: dict[str, Any]) -> bytes:
    payload = message.get("data_b64")
    if not isinstance(payload, str) or not payload:
        raise ValueError("Missing base64 payload")
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 payload") from exc


def _build_summary_payload(
    session_id: str,
    profile: LiveSessionProfile,
    bridge: GeminiLiveBridge,
) -> dict[str, Any]:
    bullets = [
        "Realtime voice tutoring is enabled.",
        "Camera frames can be streamed during the session.",
        f"Gemini transport: {'ADK' if bridge.using_adk else 'direct Vertex Live'}.",
    ]
    if profile.instrument:
        bullets.append(f"Instrument: {profile.instrument}.")
    if profile.piece:
        bullets.append(f"Piece: {profile.piece}.")
    if profile.goal:
        bullets.append(f"Goal: {profile.goal}.")
    return {
        "scenario": "live_music_tutor",
        "session_id": session_id,
        "bullets": bullets,
    }


async def _forward_bridge_events(ws: WebSocket, bridge: GeminiLiveBridge, session_id: str) -> None:
    async for event in bridge.receive():
        event_type = str(event.get("type", ""))
        if event_type:
            runtime_registry.note_outbound(session_id, event_type)
        await _send_live_event(ws, event)


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await ws.accept()

    bridge: GeminiLiveBridge | None = None
    forward_task: asyncio.Task[None] | None = None
    session_id = str(uuid4())
    profile = LiveSessionProfile()

    try:
        try:
            init_message = await ws.receive_json()
        except WebSocketDisconnect:
            return
        except (TypeError, ValueError):
            await _send_live_event(ws, ErrorEvent.from_message("Malformed websocket init message"))
            return

        if not isinstance(init_message, dict):
            await _send_live_event(ws, ErrorEvent.from_message("The first websocket message must be a JSON object"))
            return
        if str(init_message.get("type", "")).strip() != CLIENT_INIT:
            await _send_live_event(ws, ErrorEvent.from_message("The first websocket message must be client.init"))
            return

        init_payload = {key: value for key, value in init_message.items() if key != "type"}
        try:
            profile = LiveSessionProfile.model_validate(init_payload)
        except ValidationError as exc:
            await _send_live_event(ws, ErrorEvent.from_message(f"Invalid client.init payload: {exc}"))
            return
        bridge = GeminiLiveBridge(
            model_id=settings.model_id,
            location=settings.location,
            fallback_location=settings.fallback_location,
            project_id=settings.project_id,
            system_prompt=build_system_prompt(profile),
            skill="MUSIC_LIVE_TUTOR",
            goal=profile.goal,
            user_key="anonymous",
            session_key=session_id,
            prefer_adk=settings.use_adk,
        )
        await bridge.connect()
        transport = "adk" if bridge.using_adk else "direct"
        runtime_registry.start_session(session_id, profile, transport)
        runtime_registry.note_inbound(session_id, CLIENT_INIT)

        await _send_live_event(
            ws,
            ServerStatusEvent(
                payload={
                    "state": "connected",
                    "mode": profile.mode,
                    "skill": "MUSIC_LIVE_TUTOR",
                },
                metadata={
                    "transport": transport,
                    "model_id": settings.model_id,
                    "location": bridge.active_location,
                    "session_id": session_id,
                    "instrument": profile.instrument,
                    "piece": profile.piece,
                    "goal": profile.goal,
                    "camera_expected": profile.camera_expected,
                },
            ),
        )
        runtime_registry.note_outbound(session_id, "server.status")

        opening_prompt = build_opening_user_prompt(profile)
        if opening_prompt:
            await bridge.send_text(opening_prompt, role="user")

        forward_task = asyncio.create_task(_forward_bridge_events(ws, bridge, session_id))

        while True:
            try:
                message = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except (TypeError, ValueError):
                await _send_live_event(ws, ErrorEvent.from_message("Malformed JSON message"))
                continue

            if not isinstance(message, dict):
                await _send_live_event(ws, ErrorEvent.from_message("Messages must be JSON objects"))
                continue

            message_type = str(message.get("type", "")).strip()
            try:
                if message_type == CLIENT_AUDIO:
                    runtime_registry.note_inbound(session_id, message_type)
                    await bridge.send_audio(_decode_b64_payload(message))
                elif message_type == CLIENT_AUDIO_END:
                    runtime_registry.note_inbound(session_id, message_type)
                    await bridge.send_audio_end()
                elif message_type == CLIENT_VIDEO:
                    runtime_registry.note_inbound(session_id, message_type)
                    await bridge.send_image_jpeg(_decode_b64_payload(message))
                elif message_type == CLIENT_TEXT:
                    text = str(message.get("text", "")).strip()
                    if not text:
                        await _send_live_event(ws, ErrorEvent.from_message("client.text requires text"))
                        continue
                    runtime_registry.note_inbound(session_id, message_type)
                    await bridge.send_text(text, role="user")
                elif message_type == CLIENT_STOP:
                    runtime_registry.note_inbound(session_id, message_type)
                    await _send_live_event(
                        ws,
                        ServerSummaryEvent(payload=_build_summary_payload(session_id, profile, bridge)),
                    )
                    runtime_registry.note_outbound(session_id, "server.summary")
                    break
                else:
                    await _send_live_event(ws, ErrorEvent.from_message(f"Unsupported message type: {message_type}"))
            except ValueError as exc:
                await _send_live_event(ws, ErrorEvent.from_message(str(exc)))
            except Exception as exc:  # pragma: no cover - integration path
                logger.exception("Failed to process websocket message: %s", exc)
                await _send_live_event(ws, ErrorEvent.from_message("Failed to process live message"))

    except Exception as exc:  # pragma: no cover - integration path
        logger.exception("Live session error: %s", exc)
        with contextlib.suppress(Exception):
            await _send_live_event(ws, ErrorEvent.from_message(f"Live session error: {exc}"))
    finally:
        if forward_task is not None:
            forward_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await forward_task
        if bridge is not None:
            with contextlib.suppress(Exception):
                await bridge.close()
        runtime_registry.end_session(session_id)
        with contextlib.suppress(RuntimeError):
            await ws.close()
