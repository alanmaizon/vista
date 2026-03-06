from __future__ import annotations

import asyncio
import base64
import uuid
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("sqlalchemy")
pytest.importorskip("asyncpg")
pytest.importorskip("firebase_admin")
pytest.importorskip("websockets")

from fastapi.testclient import TestClient

from app import main as main_module


class FakeBridge:
    created: list["FakeBridge"] = []
    initial_events: list[dict] = []

    def __init__(self, **kwargs) -> None:
        self.model_id = kwargs["model_id"]
        self.active_location = kwargs["location"]
        self.using_adk = False
        self.system_prompt = kwargs["system_prompt"]
        self.sent_audio: list[bytes] = []
        self.sent_images: list[bytes] = []
        self.sent_text: list[tuple[str, str]] = []
        self.closed = False
        self._events: asyncio.Queue[dict | None] = asyncio.Queue()
        FakeBridge.created.append(self)

    async def connect(self) -> None:
        for event in type(self).initial_events:
            await self._events.put(event)

    async def close(self) -> None:
        self.closed = True
        await self._events.put(None)

    async def send_audio(self, payload: bytes) -> None:
        self.sent_audio.append(payload)

    async def send_image_jpeg(self, payload: bytes) -> None:
        self.sent_images.append(payload)

    async def send_text(self, text: str, *, role: str = "user") -> None:
        self.sent_text.append((text, role))

    async def receive(self):
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    FakeBridge.created = []
    FakeBridge.initial_events = []

    async def fake_init_db() -> None:
        return None

    async def fake_load_owned_session(*_args, **_kwargs):
        return SimpleNamespace(goal="Identify the arpeggio", domain="MUSIC", mode="HEAR_PHRASE")

    async def fake_noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(main_module, "GeminiLiveBridge", FakeBridge)
    monkeypatch.setattr(main_module, "init_firebase", lambda: None)
    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "adk_runtime_status", lambda: (False, "test"))
    monkeypatch.setattr(main_module, "verify_firebase_token", lambda _token: {"uid": "firebase-user"})
    monkeypatch.setattr(main_module, "_load_owned_session", fake_load_owned_session)
    monkeypatch.setattr(main_module, "_update_session_start_metadata", fake_noop)
    monkeypatch.setattr(main_module, "_persist_session_completion", fake_noop)
    monkeypatch.setattr(main_module, "_record_live_tool_call", fake_noop)

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_ws_live_rejects_invalid_session_id(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": "not-a-uuid",
                "mode": "HEAR_PHRASE",
            }
        )
        payload = ws.receive_json()

    assert payload["type"] == "error"
    assert "valid UUID" in payload["message"]


def test_ws_live_handles_audio_confirm_and_stop(client: TestClient) -> None:
    FakeBridge.initial_events = [{"type": "server.text", "text": "Play the phrase once."}]
    session_id = uuid.uuid4()

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "HEAR_PHRASE",
            }
        )
        status_payload = ws.receive_json()
        # Eurydice music runtime emits a connect hint for HEAR_PHRASE
        hint_payload = ws.receive_json()
        text_payload = ws.receive_json()

        ws.send_json(
            {
                "type": "client.audio",
                "mime": "audio/pcm;rate=16000",
                "data_b64": base64.b64encode(b"\x01\x02").decode("ascii"),
            }
        )
        ws.send_json({"type": "client.confirm"})
        # HEAR_PHRASE confirm emits a server.text event (replay request for short audio)
        confirm_event = ws.receive_json()
        ws.send_json({"type": "client.stop"})

        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]

    assert status_payload["type"] == "server.status"
    assert status_payload["state"] == "connected"
    assert status_payload["skill"] == "HEAR_PHRASE"
    assert hint_payload["type"] == "server.text"
    assert text_payload == {"type": "server.text", "text": "Play the phrase once."}
    assert confirm_event["type"] == "server.text"
    assert summary_payload["type"] == "server.summary"
    assert bridge.sent_audio == [b"\x01\x02"]
    assert bridge.closed is True


def test_ws_live_reports_invalid_base64_payload(client: TestClient) -> None:
    session_id = uuid.uuid4()

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "HEAR_PHRASE",
            }
        )
        status_payload = ws.receive_json()
        # Consume the HEAR_PHRASE connect hint
        ws.receive_json()

        ws.send_json(
            {
                "type": "client.audio",
                "mime": "audio/pcm;rate=16000",
                "data_b64": "not-base64!!",
            }
        )
        error_payload = ws.receive_json()

        ws.send_json({"type": "client.stop"})
        summary_payload = ws.receive_json()

    assert status_payload["type"] == "server.status"
    assert error_payload["type"] == "error"
    assert "Invalid base64 payload" in error_payload["message"]
    assert summary_payload["type"] == "server.summary"


def test_ws_live_injects_retrieved_context_into_system_prompt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_context(*_args, **_kwargs) -> str:
        return "PROFILE: weakest_dimension=rhythm; samples=7"

    monkeypatch.setattr(main_module, "_build_live_context_for_user", fake_context)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "HEAR_PHRASE",
            }
        )
        ws.receive_json()  # connected status
        ws.receive_json()  # HEAR_PHRASE hint
        ws.send_json({"type": "client.stop"})
        ws.receive_json()  # summary

    bridge = FakeBridge.created[0]
    assert "Retrieved session context:" in bridge.system_prompt
    assert "weakest_dimension=rhythm" in bridge.system_prompt


def test_ws_live_executes_client_tool_call_without_model_echo(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_tool_executor(*_args, **_kwargs) -> dict:
        return {"status": "ok", "measure_index": 2}

    monkeypatch.setattr(main_module, "_execute_live_tool_call", fake_tool_executor)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "HEAR_PHRASE",
            }
        )
        ws.receive_json()  # connected
        ws.receive_json()  # HEAR_PHRASE hint

        ws.send_json(
            {
                "type": "client.tool",
                "name": "lesson_step",
                "args": {"score_id": str(uuid.uuid4())},
            }
        )
        tool_payload = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        ws.receive_json()  # summary

    bridge = FakeBridge.created[0]
    assert tool_payload["type"] == "server.tool_result"
    assert tool_payload["name"] == "lesson_step"
    assert tool_payload["source"] == "client"
    assert tool_payload["ok"] is True
    assert tool_payload["result"]["status"] == "ok"
    assert bridge.sent_text == []


def test_ws_live_executes_model_tool_call_and_returns_tool_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeBridge.initial_events = [
        {
            "type": "server.tool_call",
            "name": "lesson_step",
            "args": {"score_id": str(uuid.uuid4())},
            "call_id": "call-1",
        }
    ]
    session_id = uuid.uuid4()

    async def fake_tool_executor(*_args, **_kwargs) -> dict:
        return {"lesson_stage": "awaiting-compare", "measure_index": 1}

    monkeypatch.setattr(main_module, "_execute_live_tool_call", fake_tool_executor)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "HEAR_PHRASE",
            }
        )
        ws.receive_json()  # connected
        ws.receive_json()  # HEAR_PHRASE hint
        tool_payload = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        ws.receive_json()  # summary

    bridge = FakeBridge.created[0]
    assert tool_payload["type"] == "server.tool_result"
    assert tool_payload["source"] == "model"
    assert tool_payload["name"] == "lesson_step"
    assert tool_payload["call_id"] == "call-1"
    assert tool_payload["ok"] is True
    assert "TOOL_RESULT:" in bridge.sent_text[0][0]
    assert bridge.sent_text[0][1] == "user"
