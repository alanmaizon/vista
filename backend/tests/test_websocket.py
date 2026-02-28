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
        return SimpleNamespace(goal="Find the exit sign")

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

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_ws_live_rejects_invalid_session_id(client: TestClient) -> None:
    with client.websocket_connect("/ws/live?token=test-token&session_id=not-a-uuid&mode=NAV_FIND") as ws:
        payload = ws.receive_json()

    assert payload["type"] == "error"
    assert "valid UUID" in payload["message"]


def test_ws_live_handles_audio_confirm_and_stop(client: TestClient) -> None:
    FakeBridge.initial_events = [{"type": "server.text", "text": "Hold still and look ahead."}]
    session_id = uuid.uuid4()

    with client.websocket_connect(
        f"/ws/live?token=test-token&session_id={session_id}&mode=NAV_FIND"
    ) as ws:
        status_payload = ws.receive_json()
        text_payload = ws.receive_json()

        ws.send_json(
            {
                "type": "client.audio",
                "mime": "audio/pcm;rate=16000",
                "data_b64": base64.b64encode(b"\x01\x02").decode("ascii"),
            }
        )
        ws.send_json({"type": "client.confirm"})
        ws.send_json({"type": "client.stop"})

        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    sent_texts = [text for text, _role in bridge.sent_text]

    assert status_payload["type"] == "server.status"
    assert status_payload["state"] == "connected"
    assert status_payload["skill"] == "NAV_FIND"
    assert text_payload == {"type": "server.text", "text": "Hold still and look ahead."}
    assert summary_payload["type"] == "server.summary"
    assert bridge.sent_audio == [b"\x01\x02"]
    assert any("I am starting a NAV_FIND session" in text for text in sent_texts)
    assert any("Yes, I finished that step." in text for text in sent_texts)
    assert bridge.closed is True


def test_ws_live_reports_invalid_base64_payload(client: TestClient) -> None:
    session_id = uuid.uuid4()

    with client.websocket_connect(
        f"/ws/live?token=test-token&session_id={session_id}&mode=NAV_FIND"
    ) as ws:
        status_payload = ws.receive_json()

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
