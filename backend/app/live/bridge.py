"""Gemini Live websocket bridge for Vista AI."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from time import monotonic
from typing import Any, AsyncIterator

import websockets
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request
from websockets.exceptions import ConnectionClosed


logger = logging.getLogger("vista-ai")

LIVE_API_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
LIVE_API_PATH = "/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
SUPPORTED_LOCATIONS = {"global", "us-central1", "us-east5", "europe-west4"}


def _read_field(payload: dict[str, Any], snake_name: str) -> Any:
    """Read either snake_case or lowerCamelCase from a dict."""
    if snake_name in payload:
        return payload[snake_name]
    parts = snake_name.split("_")
    camel_name = parts[0] + "".join(part.capitalize() for part in parts[1:])
    return payload.get(camel_name)


class GeminiLiveBridge:
    """Bidirectional bridge between the browser websocket and Vertex AI Live API."""

    def __init__(
        self,
        model_id: str,
        location: str,
        system_prompt: str,
        *,
        fallback_location: str = "us-central1",
        project_id: str = "",
        skill: str = "NAV_FIND",
        goal: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.location = location
        self.fallback_location = fallback_location
        self.project_id = project_id
        self.system_prompt = system_prompt
        self.skill = skill
        self.goal = goal

        self._connected = False
        self._active_location = location
        self._credentials = None
        self._auth_request = Request()
        self._upstream: Any | None = None
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False
        self._last_video_sent_at = 0.0
        self._sentinel_enqueued = False

    @property
    def active_location(self) -> str:
        return self._active_location

    async def connect(self) -> None:
        """Open a live session with Vertex AI."""
        self._closed = False
        self._sentinel_enqueued = False
        self._events = asyncio.Queue()
        last_error: Exception | None = None
        for location in self._candidate_locations():
            try:
                await self._connect_once(location)
                self._active_location = location
                self._connected = True
                return
            except Exception as exc:  # pragma: no cover - exercised via integration
                last_error = exc
                logger.warning("Live API connect failed for %s: %s", location, exc)
                await self._force_close_upstream()
        raise RuntimeError(f"Unable to connect to Vertex Live API: {last_error}") from last_error

    async def close(self) -> None:
        """Close the live session cleanly."""
        if self._closed:
            return
        self._closed = True
        self._connected = False
        await self._force_close_upstream()
        await self._enqueue_sentinel()

    async def send_audio(self, pcm16k_bytes: bytes) -> None:
        """Send raw PCM audio at 16 kHz, 16-bit LE."""
        await self._send_realtime_chunk(
            {
                "mime_type": "audio/pcm;rate=16000",
                "data": base64.b64encode(pcm16k_bytes).decode("ascii"),
            }
        )

    async def send_image_jpeg(self, jpeg_bytes: bytes) -> None:
        """Send a throttled JPEG frame (max 1 FPS)."""
        if monotonic() - self._last_video_sent_at < 1.0:
            return
        self._last_video_sent_at = monotonic()
        await self._send_realtime_chunk(
            {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(jpeg_bytes).decode("ascii"),
            }
        )

    async def send_text(self, text: str, *, role: str = "user") -> None:
        """Send a text turn to the live session."""
        if not text.strip():
            return
        await self._send_json(
            {
                "client_content": {
                    "turns": [
                        {
                            "role": role,
                            "parts": [{"text": text}],
                        }
                    ],
                    "turn_complete": True,
                }
            }
        )

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """Yield normalized browser-facing events."""
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def _connect_once(self, location: str) -> None:
        token = await self._get_access_token()
        host = f"{location}-aiplatform.googleapis.com"
        uri = f"wss://{host}{LIVE_API_PATH}"
        self._upstream = await websockets.connect(
            uri,
            additional_headers={"Authorization": f"Bearer {token}"},
            ping_interval=20,
            ping_timeout=20,
            max_size=16 * 1024 * 1024,
        )
        await self._send_json(self._setup_message(location))

        initial = await self._recv_json(timeout=10)
        if initial is not None and not self._is_setup_complete(initial):
            await self._process_json_message(initial)

        self._reader_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self) -> None:
        try:
            while self._upstream is not None:
                raw_message = await self._upstream.recv()
                if isinstance(raw_message, bytes):
                    await self._events.put(
                        {
                            "type": "server.audio",
                            "mime": "audio/pcm;rate=24000",
                            "data_b64": base64.b64encode(raw_message).decode("ascii"),
                        }
                    )
                    continue
                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning("Skipping non-JSON Live API frame")
                    continue
                await self._process_json_message(payload)
        except ConnectionClosed:
            logger.info("Live API websocket closed")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via integration
            logger.exception("Live API reader failed: %s", exc)
            await self._events.put({"type": "error", "message": f"Live API error: {exc}"})
        finally:
            self._connected = False
            await self._enqueue_sentinel()

    async def _process_json_message(self, payload: dict[str, Any]) -> None:
        if _read_field(payload, "go_away"):
            await self._events.put(
                {
                    "type": "error",
                    "message": "The upstream live session requested a reconnect.",
                }
            )
            return

        server_content = _read_field(payload, "server_content")
        if isinstance(server_content, dict):
            await self._process_server_content(server_content)

        input_transcription = _read_field(payload, "input_transcription")
        if isinstance(input_transcription, dict):
            text = _read_field(input_transcription, "text")
            if text:
                await self._events.put({"type": "server.text", "text": str(text)})

        output_transcription = _read_field(payload, "output_transcription")
        if isinstance(output_transcription, dict):
            text = _read_field(output_transcription, "text")
            if text:
                await self._events.put({"type": "server.text", "text": str(text)})

    async def _process_server_content(self, payload: dict[str, Any]) -> None:
        if _read_field(payload, "interrupted"):
            await self._events.put(
                {
                    "type": "server.status",
                    "state": "connected",
                    "mode": "NORMAL",
                    "skill": self.skill,
                }
            )

        input_transcription = _read_field(payload, "input_transcription")
        if isinstance(input_transcription, dict):
            text = _read_field(input_transcription, "text")
            if text:
                await self._events.put({"type": "server.text", "text": str(text)})

        output_transcription = _read_field(payload, "output_transcription")
        if isinstance(output_transcription, dict):
            text = _read_field(output_transcription, "text")
            if text:
                await self._events.put({"type": "server.text", "text": str(text)})

        model_turn = _read_field(payload, "model_turn")
        if not isinstance(model_turn, dict):
            return

        parts = _read_field(model_turn, "parts") or []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if text:
                await self._events.put({"type": "server.text", "text": str(text)})
            inline_data = _read_field(part, "inline_data")
            if not isinstance(inline_data, dict):
                continue
            data_b64 = inline_data.get("data")
            mime_type = _read_field(inline_data, "mime_type") or "audio/pcm;rate=24000"
            if data_b64:
                await self._events.put(
                    {
                        "type": "server.audio",
                        "mime": str(mime_type),
                        "data_b64": str(data_b64),
                    }
                )

    async def _send_realtime_chunk(self, chunk: dict[str, Any]) -> None:
        await self._send_json({"realtime_input": {"media_chunks": [chunk]}})

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self._upstream is None:
            raise RuntimeError("GeminiLiveBridge is not connected")
        await self._upstream.send(json.dumps(payload))

    async def _recv_json(self, timeout: int) -> dict[str, Any] | None:
        if self._upstream is None:
            raise RuntimeError("GeminiLiveBridge is not connected")
        while True:
            raw_message = await asyncio.wait_for(self._upstream.recv(), timeout=timeout)
            if isinstance(raw_message, bytes):
                await self._events.put(
                    {
                        "type": "server.audio",
                        "mime": "audio/pcm;rate=24000",
                        "data_b64": base64.b64encode(raw_message).decode("ascii"),
                    }
                )
                continue
            try:
                return json.loads(raw_message)
            except json.JSONDecodeError:
                logger.warning("Skipping non-JSON setup frame from Live API")

    async def _get_access_token(self) -> str:
        if self._credentials is None:
            credentials, detected_project_id = await asyncio.to_thread(
                google_auth_default,
                scopes=[LIVE_API_SCOPE],
            )
            self._credentials = credentials
            if not self.project_id:
                self.project_id = detected_project_id or ""
        if not self.project_id:
            raise RuntimeError(
                "Google Cloud project id is unavailable. Set VISTA_PROJECT_ID or GOOGLE_CLOUD_PROJECT."
            )
        await asyncio.to_thread(self._credentials.refresh, self._auth_request)
        if not self._credentials.token:
            raise RuntimeError("Unable to acquire an access token for Vertex AI")
        return str(self._credentials.token)

    def _candidate_locations(self) -> list[str]:
        candidates: list[str] = []
        preferred = self.location if self.location in SUPPORTED_LOCATIONS else self.fallback_location
        fallback = self.fallback_location if self.fallback_location in SUPPORTED_LOCATIONS else "us-central1"
        for candidate in (preferred, fallback):
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def _setup_message(self, location: str) -> dict[str, Any]:
        return {
            "setup": {
                "model": (
                    f"projects/{self.project_id}/locations/{location}/"
                    f"publishers/google/models/{self.model_id}"
                ),
                "generation_config": {
                    "response_modalities": ["audio", "text"],
                },
                "system_instruction": {
                    "parts": [{"text": self.system_prompt}],
                },
                "input_audio_transcription": {},
                "output_audio_transcription": {},
                "context_window_compression": {
                    "trigger_tokens": 12000,
                    "sliding_window": {"target_tokens": 6000},
                },
            }
        }

    @staticmethod
    def _is_setup_complete(payload: dict[str, Any]) -> bool:
        return bool(_read_field(payload, "setup_complete"))

    async def _force_close_upstream(self) -> None:
        reader_task = self._reader_task
        self._reader_task = None
        if reader_task is not None:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass
        upstream = self._upstream
        self._upstream = None
        if upstream is not None:
            await upstream.close()

    async def _enqueue_sentinel(self) -> None:
        if self._connected or self._sentinel_enqueued:
            return
        self._sentinel_enqueued = True
        await self._events.put(None)
