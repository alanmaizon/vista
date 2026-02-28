"""Main FastAPI application entry point.

This file creates a FastAPI app, registers routers, sets up startup
events to initialise Firebase, and defines a WebSocket endpoint for
real‑time interactions.  The WebSocket endpoint relies on a
`GeminiLiveBridge` instance to handle the connection to the Gemini Live
API; the actual implementation of the bridge is left for future
development in `live/bridge.py`.
"""

import json
import logging
import os
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .auth import init_firebase, get_current_user
from .sessions import router as sessions_router
from .live.bridge import GeminiLiveBridge
from .settings import settings


logger = logging.getLogger("vista-ai")

app = FastAPI(title="Vista AI Backend", version="0.1.0")
app.include_router(sessions_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise resources on application startup."""
    # Initialise Firebase once per instance
    init_firebase()
    logger.info("Firebase initialised")


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health endpoint to confirm the service is up."""
    return {"status": "ok"}


@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Handle live WebSocket connections for Vista AI.

    The client should supply three query parameters:

    - `token`: A Firebase ID token for the user
    - `session_id`: The session identifier returned from the REST API
    - `mode`: The selected skill (NAV_FIND, SHOP_VERIFY, etc.)

    Once connected, the server will delegate the stream of audio and
    optional JPEG frames to a `GeminiLiveBridge`.  Messages from the
    model are forwarded back to the client.  The connection is
    closed when the session ends or if an error occurs.
    """
    await ws.accept()
    # Extract query parameters
    token = ws.query_params.get("token")
    session_id = ws.query_params.get("session_id")
    mode = ws.query_params.get("mode", "NAV_FIND")
    if not token or not session_id:
        await ws.send_json({"type": "error", "message": "Missing token or session_id"})
        await ws.close()
        return
    # Verify token synchronously (Firebase Admin requires a blocking call)
    try:
        user = get_current_user.__wrapped__(authorization=f"Bearer {token}")  # type: ignore[attr-defined]
        # user info can be used to enforce per-user limits here
    except Exception as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close()
        return
    # Initialise the live bridge with system instructions
    bridge = GeminiLiveBridge(
        model_id=settings.model_id,
        location=settings.location,
        system_prompt=settings.system_instructions,
    )
    try:
        await bridge.connect()
    except Exception as exc:
        await ws.send_json({"type": "error", "message": f"Failed to connect: {exc}"})
        await ws.close()
        return
    # Notify client that the connection is established
    await ws.send_json({"type": "status", "state": "connected", "mode": "NORMAL", "skill": mode})
    try:
        while True:
            data = await ws.receive()
            if "type" not in data:
                # Unexpected message type, ignore or log
                continue
            # Client messages come as JSON text or bytes; decode accordingly
            if isinstance(data, str):
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "Invalid JSON message"})
                    continue
            elif isinstance(data, bytes):
                # We expect audio bytes encoded in base64 or raw; for now we ignore
                continue
            else:
                # WebSocket accepts dict but returns dict differently; we treat as bytes
                message = data
            mtype = message.get("type")
            if mtype == "client.audio":
                # Base64 decode audio
                import base64

                b64 = message.get("data_b64")
                if b64:
                    audio_bytes = base64.b64decode(b64)
                    await bridge.send_audio(audio_bytes)
            elif mtype == "client.video":
                import base64

                b64 = message.get("data_b64")
                if b64:
                    image_bytes = base64.b64decode(b64)
                    await bridge.send_image_jpeg(image_bytes)
            elif mtype == "client.confirm":
                # Confirmation could be forwarded or handled locally depending on state machine
                pass
            # Forward events from model back to client
            async for event in bridge.receive():
                await ws.send_json(event)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as exc:
        logger.error(f"Unexpected error in WebSocket: {exc}")
    finally:
        await bridge.close()
        await ws.close()