from __future__ import annotations

import asyncio
import base64
import contextlib

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
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
        self.audio_end_calls = 0
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

    async def send_audio_end(self) -> None:
        self.audio_end_calls += 1

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

    monkeypatch.setattr(main_module, "GeminiLiveBridge", FakeBridge)
    monkeypatch.setattr(main_module, "adk_runtime_status", lambda: (False, "test"))

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_health_and_runtime_endpoints(client: TestClient) -> None:
    health = client.get("/health")
    runtime = client.get("/api/runtime")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert runtime.status_code == 200
    assert runtime.json()["service"] == "eurydice-live"
    assert "/ws/live" not in runtime.json()["accepted_client_messages"]
    assert "server.audio" in runtime.json()["emitted_server_messages"]


def test_ws_live_requires_client_init(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.text", "text": "hello"})
        payload = ws.receive_json()

    assert payload["type"] == "error"
    assert "client.init" in payload["message"]


def test_ws_live_connects_and_seeds_opening_prompt(client: TestClient) -> None:
    FakeBridge.initial_events = [{"type": "server.text", "text": "What would you like to practice?"}]

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "mode": "music_tutor",
                "instrument": "voice",
                "piece": "Caro mio ben",
                "goal": "shape the opening phrase",
            }
        )
        status_payload = ws.receive_json()
        text_payload = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    assert status_payload["type"] == "server.status"
    assert status_payload["state"] == "connected"
    assert status_payload["skill"] == "MUSIC_LIVE_TUTOR"
    assert status_payload["transport"] == "direct"
    assert text_payload == {"type": "server.text", "text": "What would you like to practice?"}
    assert summary_payload["type"] == "server.summary"
    assert "bystander speech" in bridge.system_prompt
    assert "Caro mio ben" in bridge.system_prompt
    assert bridge.sent_text
    assert "Acknowledge this context" in bridge.sent_text[0][0]


def test_ws_live_forwards_audio_video_text_and_audio_end(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.init", "mode": "music_tutor"})
        ws.receive_json()  # connected

        ws.send_json(
            {
                "type": "client.audio",
                "mime": "audio/pcm;rate=16000",
                "data_b64": base64.b64encode(b"\x01\x02").decode("ascii"),
            }
        )
        ws.send_json(
            {
                "type": "client.video",
                "mime": "image/jpeg",
                "data_b64": base64.b64encode(b"\xff\xd8\xff").decode("ascii"),
            }
        )
        ws.send_json({"type": "client.text", "text": "Let's work on the first line."})
        ws.send_json({"type": "client.audio_end"})
        ws.send_json({"type": "client.stop"})
        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    assert summary_payload["type"] == "server.summary"
    assert bridge.sent_audio == [b"\x01\x02"]
    assert bridge.sent_images == [b"\xff\xd8\xff"]
    assert bridge.audio_end_calls == 1
    assert bridge.sent_text[-1] == ("Let's work on the first line.", "user")
    assert bridge.closed is True


def test_ws_live_reports_invalid_base64_payload(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.init", "mode": "music_tutor"})
        ws.receive_json()  # connected

        ws.send_json(
            {
                "type": "client.audio",
                "mime": "audio/pcm;rate=16000",
                "data_b64": "not-base64!!",
            }
        )
        error_payload = ws.receive_json()

        ws.send_json({"type": "client.stop"})
        with contextlib.suppress(Exception):
            while True:
                ws.receive_json()

    assert error_payload["type"] == "error"
    assert "Invalid base64 payload" in error_payload["message"]
