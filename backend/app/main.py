"""FastAPI entrypoint for the Ancient Greek live tutor scaffold."""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
import re
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .agents.prompts import build_system_prompt
from .agents.tools import build_default_tool_registry
from .api.router import api_router
from .api.routes.health import router as health_router
from .live.gemini_live import GeminiLiveConnection, GeminiLiveGateway
from .live.protocol import (
    ClientAudioInputEvent,
    ClientHelloEvent,
    ClientImageInputEvent,
    ClientInterruptEvent,
    ClientPingEvent,
    ClientTextInputEvent,
    ClientTurnEndEvent,
    OUTPUT_AUDIO_MIME_TYPE,
    ServerAudioOutputEvent,
    ServerSessionUpdateEvent,
    ServerStatusEvent,
    ServerTextOutputEvent,
    ServerToolCallEvent,
    ServerToolResultEvent,
    ServerTranscriptEvent,
    ServerTurnEvent,
    ValidationError,
    build_server_error_event,
    build_server_ready_event,
    event_to_wire,
    parse_client_event,
)
from .settings import get_settings


logger = logging.getLogger("ancient_greek.live")
settings = get_settings()
gemini_gateway = GeminiLiveGateway(settings)
tool_registry = build_default_tool_registry()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    summary="Scaffold for a voice-first multimodal Ancient Greek tutor.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router)

_SECONDS_DURATION_RE = re.compile(r"^(?P<seconds>\d+(?:\.\d+)?)s$")


def _decode_base64_payload(payload: str, *, field_name: str) -> bytes:
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{field_name} is not valid base64") from exc


def _parse_duration_to_ms(duration: str | None) -> int | None:
    if not duration:
        return None
    match = _SECONDS_DURATION_RE.match(duration.strip())
    if not match:
        return None
    return int(float(match.group("seconds")) * 1000)


def _normalize_function_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            return {"raw_args": raw_args}
        if isinstance(parsed, dict):
            return parsed
        return {"raw_args": parsed}
    return {"raw_args": raw_args}


def _tool_not_implemented_response(tool_name: str) -> dict[str, Any]:
    return {
        "status": "NOT_IMPLEMENTED",
        "message": (
            f"Tool '{tool_name}' is registered but executable logic is not implemented yet in this "
            "bridge iteration."
        ),
    }


async def send_live_event(
    websocket: WebSocket,
    event: object,
    *,
    send_lock: asyncio.Lock,
) -> None:
    if not hasattr(event, "model_dump"):
        raise TypeError("Expected a live event model")
    payload = event_to_wire(event)
    async with send_lock:
        await websocket.send_json(payload)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "scaffold",
        "docs": "/docs",
        "health": "/healthz",
        "runtime": "/api/runtime",
    }


@app.websocket(settings.websocket_path)
async def live_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    send_lock = asyncio.Lock()
    connection_id = f"conn-{uuid4().hex[:10]}"
    state = {
        "session_id": None,
        "last_turn_id": "turn-initial",
        "audio_chunk_index": 0,
    }

    gemini_connection: GeminiLiveConnection | None = None
    gemini_receive_task: asyncio.Task[None] | None = None

    async def emit(event: object) -> None:
        await send_live_event(websocket, event, send_lock=send_lock)

    async def close_gemini_connection() -> None:
        nonlocal gemini_connection, gemini_receive_task

        if gemini_receive_task is not None:
            gemini_receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await gemini_receive_task
            gemini_receive_task = None

        if gemini_connection is not None:
            try:
                await gemini_connection.close()
            finally:
                gemini_connection = None

    async def send_tool_response_to_gemini(
        tool_call_id: str,
        tool_name: str,
        response: dict[str, Any],
    ) -> None:
        if gemini_connection is None:
            return
        try:
            await gemini_connection.send_tool_response(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                response=response,
            )
        except Exception:
            logger.exception("Failed sending tool response to Gemini")
            await emit(
                build_server_error_event(
                    "GEMINI_TOOL_RESPONSE_FAILED",
                    "Failed sending tool response back to Gemini Live.",
                    retryable=True,
                    session_id=state["session_id"],
                )
            )

    async def handle_gemini_function_call(function_call: Any) -> None:
        tool_call_id = getattr(function_call, "id", None) or f"tool-{uuid4().hex[:10]}"
        tool_name = getattr(function_call, "name", None) or "unknown_tool"
        raw_args = getattr(function_call, "args", None)
        args = _normalize_function_args(raw_args)
        turn_id = state["last_turn_id"]

        await emit(
            ServerToolCallEvent(
                session_id=state["session_id"] or "session-unknown",
                turn_id=turn_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=args,
                status="requested",
            )
        )

        placeholder_response = _tool_not_implemented_response(tool_name)
        await emit(
            ServerToolResultEvent(
                session_id=state["session_id"] or "session-unknown",
                turn_id=turn_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                status="failed",
                result=placeholder_response,
                error="NOT_IMPLEMENTED",
            )
        )
        await send_tool_response_to_gemini(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            response=placeholder_response,
        )

    async def pump_gemini_messages() -> None:
        if gemini_connection is None:
            return

        try:
            async for message in gemini_connection.receive():
                setup_complete = getattr(message, "setup_complete", None)
                if setup_complete is not None:
                    upstream_session_id = getattr(setup_complete, "session_id", None)
                    detail = "Gemini Live setup complete."
                    if upstream_session_id:
                        detail = f"{detail} upstream_session_id={upstream_session_id}"
                    await emit(
                        ServerStatusEvent(
                            phase="ready",
                            detail=detail,
                            session_id=state["session_id"],
                            resumable=True,
                        )
                    )

                server_content = getattr(message, "server_content", None)
                if server_content is not None:
                    input_transcription = getattr(server_content, "input_transcription", None)
                    if input_transcription and getattr(input_transcription, "text", None):
                        await emit(
                            ServerTranscriptEvent(
                                session_id=state["session_id"] or "session-unknown",
                                turn_id=state["last_turn_id"],
                                speaker="learner",
                                source="input_audio",
                                text=str(input_transcription.text),
                                is_final=bool(getattr(input_transcription, "finished", False)),
                            )
                        )

                    output_transcription = getattr(server_content, "output_transcription", None)
                    if output_transcription and getattr(output_transcription, "text", None):
                        await emit(
                            ServerTranscriptEvent(
                                session_id=state["session_id"] or "session-unknown",
                                turn_id=state["last_turn_id"],
                                speaker="tutor",
                                source="output_audio_transcription",
                                text=str(output_transcription.text),
                                is_final=bool(getattr(output_transcription, "finished", False)),
                                interrupted=bool(getattr(server_content, "interrupted", False)),
                            )
                        )

                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn is not None:
                        parts = getattr(model_turn, "parts", None) or []
                        for part in parts:
                            if getattr(part, "text", None):
                                tutor_text = str(part.text)
                                is_final = bool(
                                    getattr(server_content, "generation_complete", False)
                                    or getattr(server_content, "turn_complete", False)
                                )
                                await emit(
                                    ServerTextOutputEvent(
                                        session_id=state["session_id"] or "session-unknown",
                                        turn_id=state["last_turn_id"],
                                        text=tutor_text,
                                        is_final=is_final,
                                    )
                                )
                                await emit(
                                    ServerTranscriptEvent(
                                        session_id=state["session_id"] or "session-unknown",
                                        turn_id=state["last_turn_id"],
                                        speaker="tutor",
                                        source="output_text",
                                        text=tutor_text,
                                        is_final=is_final,
                                        interrupted=bool(getattr(server_content, "interrupted", False)),
                                    )
                                )

                            inline_data = getattr(part, "inline_data", None)
                            if inline_data and getattr(inline_data, "data", None):
                                mime_type = getattr(inline_data, "mime_type", None) or OUTPUT_AUDIO_MIME_TYPE
                                if mime_type.startswith("audio/"):
                                    chunk_index = state["audio_chunk_index"]
                                    state["audio_chunk_index"] += 1
                                    data_base64 = base64.b64encode(inline_data.data).decode("ascii")
                                    is_final_chunk = bool(
                                        getattr(server_content, "generation_complete", False)
                                        or getattr(server_content, "turn_complete", False)
                                    )
                                    await emit(
                                        ServerAudioOutputEvent(
                                            session_id=state["session_id"] or "session-unknown",
                                            turn_id=state["last_turn_id"],
                                            chunk_index=chunk_index,
                                            mime_type=mime_type,
                                            data_base64=data_base64,
                                            is_final_chunk=is_final_chunk,
                                        )
                                    )
                                    await emit(
                                        ServerStatusEvent(
                                            phase="speaking",
                                            detail=f"Streaming tutor audio chunk {chunk_index}.",
                                            session_id=state["session_id"],
                                            turn_id=state["last_turn_id"],
                                        )
                                    )

                    if getattr(server_content, "interrupted", False):
                        await emit(
                            ServerTurnEvent(
                                session_id=state["session_id"] or "session-unknown",
                                turn_id=state["last_turn_id"],
                                event="interrupted",
                                detail="Gemini signaled an interrupted generation.",
                            )
                        )

                    if getattr(server_content, "generation_complete", False):
                        await emit(
                            ServerTurnEvent(
                                session_id=state["session_id"] or "session-unknown",
                                turn_id=state["last_turn_id"],
                                event="generation_complete",
                                detail="Gemini generation completed for the current turn.",
                            )
                        )

                    if getattr(server_content, "turn_complete", False):
                        await emit(
                            ServerTurnEvent(
                                session_id=state["session_id"] or "session-unknown",
                                turn_id=state["last_turn_id"],
                                event="turn_complete",
                                detail="Gemini turn complete.",
                            )
                        )

                    if getattr(server_content, "waiting_for_input", False):
                        await emit(
                            ServerStatusEvent(
                                phase="listening",
                                detail="Gemini is waiting for learner input.",
                                session_id=state["session_id"],
                            )
                        )

                tool_call = getattr(message, "tool_call", None)
                if tool_call is not None:
                    function_calls = getattr(tool_call, "function_calls", None) or []
                    for function_call in function_calls:
                        await handle_gemini_function_call(function_call)

                tool_call_cancellation = getattr(message, "tool_call_cancellation", None)
                if tool_call_cancellation is not None:
                    call_ids = getattr(tool_call_cancellation, "ids", None) or []
                    if call_ids:
                        await emit(
                            ServerStatusEvent(
                                phase="tool_running",
                                detail=f"Gemini canceled tool calls: {', '.join(call_ids)}.",
                                session_id=state["session_id"],
                                turn_id=state["last_turn_id"],
                            )
                        )

                session_resumption_update = getattr(message, "session_resumption_update", None)
                if session_resumption_update is not None:
                    await emit(
                        ServerSessionUpdateEvent(
                            session_id=state["session_id"],
                            resumption_handle=getattr(session_resumption_update, "new_handle", None),
                            go_away=False,
                        )
                    )

                go_away = getattr(message, "go_away", None)
                if go_away is not None:
                    time_left_ms = _parse_duration_to_ms(getattr(go_away, "time_left", None))
                    await emit(
                        ServerSessionUpdateEvent(
                            session_id=state["session_id"],
                            go_away=True,
                            time_left_ms=time_left_ms,
                        )
                    )
                    await emit(
                        ServerStatusEvent(
                            phase="closing",
                            detail="Gemini sent a go-away signal. Prepare to reconnect or resume.",
                            session_id=state["session_id"],
                            resumable=True,
                        )
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Gemini receive loop failed")
            await emit(
                build_server_error_event(
                    "GEMINI_RECEIVE_FAILED",
                    "Gemini live receive loop failed.",
                    retryable=True,
                    session_id=state["session_id"],
                )
            )

    await emit(
        build_server_ready_event(connection_id=connection_id, websocket_path=settings.websocket_path),
    )

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                await emit(
                    build_server_error_event(
                        "UNSUPPORTED_BINARY_FRAME",
                        "The websocket contract expects JSON frames, not raw binary frames.",
                        retryable=False,
                        session_id=state["session_id"],
                    ),
                )
                continue

            raw_text = message.get("text")
            if raw_text is None:
                continue

            try:
                raw_event = json.loads(raw_text)
            except json.JSONDecodeError:
                await emit(
                    build_server_error_event(
                        "INVALID_JSON",
                        "Incoming websocket frame was not valid JSON.",
                        retryable=False,
                        session_id=state["session_id"],
                    ),
                )
                continue

            try:
                event = parse_client_event(raw_event)
            except ValidationError as exc:
                await emit(
                    build_server_error_event(
                        "INVALID_CLIENT_EVENT",
                        "Incoming websocket event did not match the live protocol contract.",
                        retryable=False,
                        session_id=state["session_id"],
                        detail={"errors": exc.errors()},
                    ),
                )
                continue

            if isinstance(event, ClientHelloEvent):
                await close_gemini_connection()
                state["session_id"] = event.session_id or f"session-{uuid4().hex[:10]}"
                state["audio_chunk_index"] = 0
                state["last_turn_id"] = "turn-initial"

                await emit(
                    ServerStatusEvent(
                        phase="ready",
                        detail=(
                            "Handshake accepted. Attempting Gemini Live connection for this session."
                        ),
                        session_id=state["session_id"],
                        resumable=True,
                    )
                )

                mode = event.mode or settings.default_tutoring_mode
                response_language = event.preferred_response_language or "English"
                system_prompt = build_system_prompt(
                    mode=mode,
                    response_language=response_language,
                )
                tools = tool_registry.list_definitions()

                try:
                    gemini_connection = await asyncio.wait_for(
                        gemini_gateway.connect_session(
                            system_prompt=system_prompt,
                            tools=tools,
                        ),
                        timeout=settings.gemini_connect_timeout_seconds,
                    )
                except Exception as exc:
                    logger.warning("Gemini live connect failed: %s", exc)
                    await emit(
                        build_server_error_event(
                            "GEMINI_CONNECT_FAILED",
                            (
                                "Gemini Live connection failed; continuing in scaffold mode for this "
                                "websocket session."
                            ),
                            retryable=True,
                            session_id=state["session_id"],
                            detail={"reason": str(exc)},
                        )
                    )
                    gemini_connection = None
                else:
                    gemini_receive_task = asyncio.create_task(pump_gemini_messages())
                    await emit(
                        ServerStatusEvent(
                            phase="listening",
                            detail=f"Connected to Gemini Live model {settings.gemini_live_model}.",
                            session_id=state["session_id"],
                            resumable=True,
                        )
                    )
                continue

            if state["session_id"] is None:
                await emit(
                    build_server_error_event(
                        "HELLO_REQUIRED",
                        "Send client.hello before any input events.",
                        retryable=True,
                    ),
                )
                continue

            if isinstance(event, ClientTextInputEvent):
                state["last_turn_id"] = event.turn_id
                await emit(
                    ServerTranscriptEvent(
                        session_id=state["session_id"],
                        turn_id=event.turn_id,
                        speaker="learner",
                        source="input_text",
                        text=event.text,
                        is_final=event.is_final,
                    ),
                )
                if gemini_connection is None:
                    await emit(
                        ServerStatusEvent(
                            phase="receiving_input",
                            detail="Received learner text input in scaffold mode.",
                            session_id=state["session_id"],
                            turn_id=event.turn_id,
                        )
                    )
                    continue
                try:
                    await gemini_connection.send_text(event.text)
                except Exception:
                    logger.exception("Failed forwarding text input to Gemini")
                    await emit(
                        build_server_error_event(
                            "GEMINI_SEND_TEXT_FAILED",
                            "Failed forwarding learner text to Gemini Live.",
                            retryable=True,
                            session_id=state["session_id"],
                            detail={"turn_id": event.turn_id},
                        )
                    )
                continue

            if isinstance(event, ClientAudioInputEvent):
                state["last_turn_id"] = event.turn_id
                if gemini_connection is None:
                    await emit(
                        ServerStatusEvent(
                            phase="receiving_input",
                            detail=f"Received audio chunk {event.chunk_index} in scaffold mode.",
                            session_id=state["session_id"],
                            turn_id=event.turn_id,
                        )
                    )
                    continue
                try:
                    audio_bytes = _decode_base64_payload(
                        event.data_base64,
                        field_name="client.input.audio.data_base64",
                    )
                except ValueError as exc:
                    await emit(
                        build_server_error_event(
                            "INVALID_AUDIO_BASE64",
                            str(exc),
                            retryable=False,
                            session_id=state["session_id"],
                            detail={"turn_id": event.turn_id, "chunk_index": event.chunk_index},
                        )
                    )
                    continue
                try:
                    await gemini_connection.send_audio_chunk(
                        audio_bytes=audio_bytes,
                        mime_type=event.mime_type,
                        is_final_chunk=event.is_final_chunk,
                    )
                except Exception:
                    logger.exception("Failed forwarding audio input to Gemini")
                    await emit(
                        build_server_error_event(
                            "GEMINI_SEND_AUDIO_FAILED",
                            "Failed forwarding learner audio to Gemini Live.",
                            retryable=True,
                            session_id=state["session_id"],
                            detail={"turn_id": event.turn_id, "chunk_index": event.chunk_index},
                        )
                    )
                continue

            if isinstance(event, ClientImageInputEvent):
                state["last_turn_id"] = event.turn_id
                if gemini_connection is None:
                    await emit(
                        ServerStatusEvent(
                            phase="receiving_input",
                            detail=(
                                f"Received {event.source} frame {event.frame_index} in scaffold mode."
                            ),
                            session_id=state["session_id"],
                            turn_id=event.turn_id,
                        )
                    )
                    continue
                try:
                    image_bytes = _decode_base64_payload(
                        event.data_base64,
                        field_name="client.input.image.data_base64",
                    )
                except ValueError as exc:
                    await emit(
                        build_server_error_event(
                            "INVALID_IMAGE_BASE64",
                            str(exc),
                            retryable=False,
                            session_id=state["session_id"],
                            detail={"turn_id": event.turn_id, "frame_index": event.frame_index},
                        )
                    )
                    continue
                try:
                    await gemini_connection.send_image_chunk(
                        image_bytes=image_bytes,
                        mime_type=event.mime_type,
                    )
                except Exception:
                    logger.exception("Failed forwarding image input to Gemini")
                    await emit(
                        build_server_error_event(
                            "GEMINI_SEND_IMAGE_FAILED",
                            "Failed forwarding image input to Gemini Live.",
                            retryable=True,
                            session_id=state["session_id"],
                            detail={"turn_id": event.turn_id, "frame_index": event.frame_index},
                        )
                    )
                continue

            if isinstance(event, ClientTurnEndEvent):
                state["last_turn_id"] = event.turn_id
                await emit(
                    ServerTurnEvent(
                        session_id=state["session_id"],
                        turn_id=event.turn_id,
                        event="learner_turn_closed",
                        detail=f"Learner turn ended because: {event.reason}.",
                    )
                )
                await emit(
                    ServerStatusEvent(
                        phase="thinking",
                        detail="Learner turn closed. Awaiting tutor generation.",
                        session_id=state["session_id"],
                        turn_id=event.turn_id,
                    )
                )
                if gemini_connection is not None:
                    try:
                        await gemini_connection.end_turn()
                    except Exception:
                        logger.exception("Failed signaling turn end to Gemini")
                        await emit(
                            build_server_error_event(
                                "GEMINI_TURN_END_FAILED",
                                "Failed signaling learner turn end to Gemini Live.",
                                retryable=True,
                                session_id=state["session_id"],
                                detail={"turn_id": event.turn_id},
                            )
                        )
                continue

            if isinstance(event, ClientInterruptEvent):
                await emit(
                    ServerStatusEvent(
                        phase="interrupted",
                        detail=f"Interrupt received from the client: {event.reason}.",
                        session_id=state["session_id"],
                        turn_id=event.turn_id,
                    )
                )
                await emit(
                    ServerTurnEvent(
                        session_id=state["session_id"],
                        turn_id=event.turn_id or state["last_turn_id"],
                        event="interrupted",
                        detail="Client requested that current playback or generation stop.",
                    )
                )
                if gemini_connection is not None:
                    try:
                        await gemini_connection.end_turn()
                    except Exception:
                        logger.exception("Failed forwarding interrupt to Gemini")
                        await emit(
                            build_server_error_event(
                                "GEMINI_INTERRUPT_FAILED",
                                "Failed forwarding interrupt signal to Gemini Live.",
                                retryable=True,
                                session_id=state["session_id"],
                            )
                        )
                continue

            if isinstance(event, ClientPingEvent):
                await emit(
                    ServerStatusEvent(
                        phase="listening",
                        detail="pong",
                        session_id=state["session_id"],
                    )
                )
    except WebSocketDisconnect:
        return
    finally:
        await close_gemini_connection()
