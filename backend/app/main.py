"""FastAPI entrypoint for the Ancient Greek live tutor scaffold."""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .api.routes.health import router as health_router
from .settings import get_settings


settings = get_settings()
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
    await websocket.send_json(
        {
            "type": "server.status",
            "status": "scaffold",
            "message": (
                "Live transport is not wired to Gemini yet. "
                "This websocket exists so the client can be built against a stable path."
            ),
        }
    )

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text"):
                await websocket.send_json(
                    {
                        "type": "server.ack",
                        "status": "placeholder",
                        "received": "text",
                        "preview": message["text"][:120],
                    }
                )
            elif message.get("bytes") is not None:
                await websocket.send_json(
                    {
                        "type": "server.ack",
                        "status": "placeholder",
                        "received": "bytes",
                        "byte_length": len(message["bytes"]),
                    }
                )
    except WebSocketDisconnect:
        return

