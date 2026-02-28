"""Gemini Live bridge for Vista AI.

This module prefers Google's ADK live streaming stack when available,
while preserving the existing direct Vertex Live websocket path as a
fallback. The public ``GeminiLiveBridge`` API stays stable for the
rest of the application.
"""

from __future__ import annotations

import asyncio
import base64
import importlib
import inspect
import json
import logging
import os
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


def _candidate_locations(location: str, fallback_location: str) -> list[str]:
    candidates: list[str] = []
    preferred = location if location in SUPPORTED_LOCATIONS else fallback_location
    fallback = fallback_location if fallback_location in SUPPORTED_LOCATIONS else "us-central1"
    for candidate in (preferred, fallback):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class _DirectGeminiLiveBridge:
    """Direct Vertex Live websocket implementation."""

    def __init__(
        self,
        *,
        model_id: str,
        location: str,
        fallback_location: str,
        project_id: str,
        system_prompt: str,
        skill: str,
        goal: str | None,
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
        self._closed = False
        self._sentinel_enqueued = False
        self._events = asyncio.Queue()
        last_error: Exception | None = None
        for location in _candidate_locations(self.location, self.fallback_location):
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
        if self._closed:
            return
        self._closed = True
        self._connected = False
        await self._force_close_upstream()
        await self._enqueue_sentinel()

    async def send_audio(self, pcm16k_bytes: bytes) -> None:
        await self._send_realtime_chunk(
            {
                "mime_type": "audio/pcm;rate=16000",
                "data": base64.b64encode(pcm16k_bytes).decode("ascii"),
            }
        )

    async def send_image_jpeg(self, jpeg_bytes: bytes) -> None:
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


class _AdkGeminiLiveBridge:
    """ADK-backed Gemini Live implementation."""

    def __init__(
        self,
        *,
        model_id: str,
        location: str,
        fallback_location: str,
        project_id: str,
        system_prompt: str,
        skill: str,
        goal: str | None,
        user_key: str,
        session_key: str,
    ) -> None:
        self.model_id = model_id
        self.location = location
        self.fallback_location = fallback_location
        self.project_id = project_id
        self.system_prompt = system_prompt
        self.skill = skill
        self.goal = goal
        self.user_key = user_key or "vista-user"
        self.session_key = session_key or f"vista-live-{int(monotonic() * 1000)}"

        self._active_location = _candidate_locations(location, fallback_location)[0]
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._live_request_queue: Any | None = None
        self._closed = False
        self._connected = False
        self._sentinel_enqueued = False
        self._last_video_sent_at = 0.0
        self._run_config: Any = None
        self._runner: Any = None
        self._types: Any = None

    @property
    def active_location(self) -> str:
        return self._active_location

    async def connect(self) -> None:
        self._closed = False
        self._sentinel_enqueued = False
        self._events = asyncio.Queue()

        self._configure_vertex_environment()
        (
            agent_cls,
            live_request_queue_cls,
            run_config_cls,
            streaming_mode,
            runner_cls,
            in_memory_session_service_cls,
            types_module,
        ) = self._import_adk_modules()
        self._types = types_module

        session_service = in_memory_session_service_cls()
        app_name = "vista-ai-live"
        existing_session = None
        if hasattr(session_service, "get_session"):
            existing_session = await _maybe_await(
                session_service.get_session(
                    app_name=app_name,
                    user_id=self.user_key,
                    session_id=self.session_key,
                )
            )
        if existing_session is None:
            await _maybe_await(
                session_service.create_session(
                    app_name=app_name,
                    user_id=self.user_key,
                    session_id=self.session_key,
                )
            )

        agent = agent_cls(
            name="vista_live_agent",
            model=self.model_id,
            instruction=self.system_prompt,
            description=f"Vista AI live session for {self.skill}",
        )
        self._runner = runner_cls(
            app_name=app_name,
            agent=agent,
            session_service=session_service,
        )
        self._live_request_queue = live_request_queue_cls()
        self._run_config = self._build_run_config(run_config_cls, streaming_mode, types_module)
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._connected = True

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._connected = False

        if self._live_request_queue is not None and hasattr(self._live_request_queue, "close"):
            await _maybe_await(self._live_request_queue.close())

        reader_task = self._reader_task
        self._reader_task = None
        if reader_task is not None:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass

        await self._enqueue_sentinel()

    async def send_audio(self, pcm16k_bytes: bytes) -> None:
        self._require_ready()
        await _maybe_await(
            self._live_request_queue.send_realtime(
                self._types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=pcm16k_bytes,
                )
            )
        )

    async def send_image_jpeg(self, jpeg_bytes: bytes) -> None:
        self._require_ready()
        if monotonic() - self._last_video_sent_at < 1.0:
            return
        self._last_video_sent_at = monotonic()
        await _maybe_await(
            self._live_request_queue.send_realtime(
                self._types.Blob(
                    mime_type="image/jpeg",
                    data=jpeg_bytes,
                )
            )
        )

    async def send_text(self, text: str, *, role: str = "user") -> None:
        self._require_ready()
        if not text.strip():
            return
        content = self._types.Content(
            role=role,
            parts=[self._types.Part(text=text)],
        )
        await _maybe_await(self._live_request_queue.send_content(content=content))

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def _reader_loop(self) -> None:
        try:
            async for event in self._runner.run_live(
                user_id=self.user_key,
                session_id=self.session_key,
                live_request_queue=self._live_request_queue,
                run_config=self._run_config,
            ):
                await self._process_adk_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via integration
            logger.exception("ADK Live reader failed: %s", exc)
            await self._events.put({"type": "error", "message": f"ADK Live error: {exc}"})
        finally:
            self._connected = False
            await self._enqueue_sentinel()

    async def _process_adk_event(self, event: Any) -> None:
        if getattr(event, "interrupted", False):
            await self._events.put(
                {
                    "type": "server.status",
                    "state": "connected",
                    "mode": "NORMAL",
                    "skill": self.skill,
                }
            )

        if getattr(event, "error_code", None) or getattr(event, "error_message", None):
            await self._events.put(
                {
                    "type": "error",
                    "message": getattr(event, "error_message", "Unknown ADK live error"),
                }
            )
            return

        content = getattr(event, "content", None)
        if content is None:
            return

        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text and not getattr(event, "partial", False):
                await self._events.put({"type": "server.text", "text": str(text)})

            inline_data = getattr(part, "inline_data", None)
            if inline_data is None:
                continue

            mime_type = getattr(inline_data, "mime_type", "") or "audio/pcm;rate=24000"
            data = getattr(inline_data, "data", None)
            if not data:
                continue

            if isinstance(data, str):
                data_b64 = data
            else:
                data_b64 = base64.b64encode(bytes(data)).decode("ascii")

            await self._events.put(
                {
                    "type": "server.audio",
                    "mime": str(mime_type),
                    "data_b64": data_b64,
                }
            )

    def _configure_vertex_environment(self) -> None:
        if not self.project_id:
            raise RuntimeError(
                "Google Cloud project id is unavailable. Set VISTA_PROJECT_ID or GOOGLE_CLOUD_PROJECT."
            )
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = self._active_location
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")

    def _import_adk_modules(self) -> tuple[Any, Any, Any, Any, Any, Any, Any]:
        try:
            agent_cls = importlib.import_module("google.adk.agents").Agent
            live_request_queue_cls = importlib.import_module(
                "google.adk.agents.live_request_queue"
            ).LiveRequestQueue
            run_config_module = importlib.import_module("google.adk.agents.run_config")
            runner_cls = importlib.import_module("google.adk.runners").Runner
            in_memory_session_service_cls = importlib.import_module(
                "google.adk.sessions"
            ).InMemorySessionService
            types_module = importlib.import_module("google.genai.types")
        except Exception as exc:
            raise RuntimeError("google-adk is not available") from exc

        return (
            agent_cls,
            live_request_queue_cls,
            run_config_module.RunConfig,
            run_config_module.StreamingMode,
            runner_cls,
            in_memory_session_service_cls,
            types_module,
        )

    def _build_run_config(self, run_config_cls: Any, streaming_mode: Any, types_module: Any) -> Any:
        kwargs: dict[str, Any] = {
            "streaming_mode": getattr(streaming_mode, "BIDI", streaming_mode),
        }
        kwargs["response_modalities"] = ["AUDIO"]
        if hasattr(types_module, "AudioTranscriptionConfig"):
            kwargs["input_audio_transcription"] = types_module.AudioTranscriptionConfig()
            kwargs["output_audio_transcription"] = types_module.AudioTranscriptionConfig()
        if hasattr(types_module, "SessionResumptionConfig"):
            kwargs["session_resumption"] = types_module.SessionResumptionConfig()
        return run_config_cls(**kwargs)

    def _require_ready(self) -> None:
        if not self._connected or self._live_request_queue is None or self._types is None:
            raise RuntimeError("GeminiLiveBridge is not connected")

    async def _enqueue_sentinel(self) -> None:
        if self._connected or self._sentinel_enqueued:
            return
        self._sentinel_enqueued = True
        await self._events.put(None)


class GeminiLiveBridge:
    """Bidirectional bridge that prefers ADK and falls back to direct Live API."""

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
        user_key: str = "",
        session_key: str = "",
        prefer_adk: bool = True,
    ) -> None:
        self.model_id = model_id
        self.location = location
        self.fallback_location = fallback_location
        self.project_id = project_id
        self.system_prompt = system_prompt
        self.skill = skill
        self.goal = goal
        self.user_key = user_key
        self.session_key = session_key
        self.prefer_adk = prefer_adk
        self._impl: _AdkGeminiLiveBridge | _DirectGeminiLiveBridge | None = None

    @property
    def active_location(self) -> str:
        if self._impl is None:
            return self.location
        return self._impl.active_location

    @property
    def using_adk(self) -> bool:
        return isinstance(self._impl, _AdkGeminiLiveBridge)

    async def connect(self) -> None:
        if self.prefer_adk:
            try:
                adk_impl = _AdkGeminiLiveBridge(
                    model_id=self.model_id,
                    location=self.location,
                    fallback_location=self.fallback_location,
                    project_id=self.project_id,
                    system_prompt=self.system_prompt,
                    skill=self.skill,
                    goal=self.goal,
                    user_key=self.user_key,
                    session_key=self.session_key,
                )
                await adk_impl.connect()
                self._impl = adk_impl
                logger.info("Using ADK live bridge")
                return
            except Exception as exc:  # pragma: no cover - exercised via integration
                logger.warning("ADK live bridge unavailable, falling back to direct bridge: %s", exc)

        direct_impl = _DirectGeminiLiveBridge(
            model_id=self.model_id,
            location=self.location,
            fallback_location=self.fallback_location,
            project_id=self.project_id,
            system_prompt=self.system_prompt,
            skill=self.skill,
            goal=self.goal,
        )
        await direct_impl.connect()
        self._impl = direct_impl

    async def close(self) -> None:
        if self._impl is None:
            return
        await self._impl.close()

    async def send_audio(self, pcm16k_bytes: bytes) -> None:
        self._require_impl()
        await self._impl.send_audio(pcm16k_bytes)

    async def send_image_jpeg(self, jpeg_bytes: bytes) -> None:
        self._require_impl()
        await self._impl.send_image_jpeg(jpeg_bytes)

    async def send_text(self, text: str, *, role: str = "user") -> None:
        self._require_impl()
        await self._impl.send_text(text, role=role)

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        self._require_impl()
        async for event in self._impl.receive():
            yield event

    def _require_impl(self) -> None:
        if self._impl is None:
            raise RuntimeError("GeminiLiveBridge is not connected")
