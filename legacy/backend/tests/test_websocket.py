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
    audio_end_events: list[dict] = []

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
        for event in type(self).audio_end_events:
            await self._events.put(event)

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
    FakeBridge.audio_end_events = []

    monkeypatch.setattr(main_module, "GeminiLiveBridge", FakeBridge)
    monkeypatch.setattr(main_module, "adk_runtime_status", lambda: (False, "test"))

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_health_and_runtime_endpoints(client: TestClient) -> None:
    health = client.get("/health")
    runtime = client.get("/api/runtime")
    debug = client.get("/api/runtime/debug")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert runtime.status_code == 200
    assert runtime.json()["service"] == "eurydice-live"
    assert "service_name" in runtime.json()
    assert "revision_name" in runtime.json()
    assert "instance_id" in runtime.json()
    assert runtime.json()["active_session_count"] == 0
    assert "/ws/live" not in runtime.json()["accepted_client_messages"]
    assert "server.audio" in runtime.json()["emitted_server_messages"]
    assert debug.status_code == 200
    assert "service_name" in debug.json()
    assert "revision_name" in debug.json()
    assert "instance_id" in debug.json()
    assert debug.json()["active_sessions"] == []


def test_session_profile_endpoint_normalizes_values(client: TestClient) -> None:
    response = client.post(
        "/api/live/session-profile",
        json={
            "mode": "Technique Practice",
            "instrument": "  Voice  ",
            "piece": "  Caro   mio ben ",
            "goal": " shape   the opening phrase ",
            "camera_expected": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_profile"]["mode"] == "technique_practice"
    assert payload["session_profile"]["instrument"] == "Voice"
    assert payload["session_profile"]["piece"] == "Caro mio ben"
    assert payload["session_profile"]["goal"] == "shape the opening phrase"
    assert payload["session_profile"]["camera_expected"] is True
    assert payload["label"] == "Voice · Caro mio ben · shape the opening phrase"
    assert "camera_expected=true" in payload["opening_hint"]


def test_ws_live_requires_client_init(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.text", "text": "hello"})
        payload = ws.receive_json()

    assert payload["type"] == "error"
    assert "client.init" in payload["message"]


def test_ws_live_rejects_invalid_init_payload(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.init", "mode": "totally invalid"})
        payload = ws.receive_json()

    assert payload["type"] == "error"
    assert "Invalid client.init payload" in payload["message"]


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
                "camera_expected": True,
            }
        )
        status_payload = ws.receive_json()
        debug_payload = client.get("/api/runtime/debug").json()
        text_payload = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    assert status_payload["type"] == "server.status"
    assert status_payload["state"] == "connected"
    assert status_payload["skill"] == "MUSIC_LIVE_TUTOR"
    assert status_payload["transport"] == "direct"
    assert isinstance(status_payload["session_id"], str)
    assert status_payload["camera_expected"] is True
    assert text_payload == {"type": "server.text", "text": "What would you like to practice?"}
    assert summary_payload["type"] == "server.summary"
    assert summary_payload["session_id"] == status_payload["session_id"]
    assert "bystander speech" in bridge.system_prompt
    assert "Caro mio ben" in bridge.system_prompt
    assert "camera at music notation" in bridge.system_prompt
    assert bridge.sent_text
    assert "Acknowledge this context" in bridge.sent_text[0][0]
    assert debug_payload["active_session_count"] == 1
    assert debug_payload["active_sessions"][0]["session_id"] == status_payload["session_id"]
    assert debug_payload["active_sessions"][0]["camera_expected"] is True


def test_ws_live_forwards_audio_video_text_and_audio_end(client: TestClient) -> None:
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.init", "mode": "music_tutor"})
        status_payload = ws.receive_json()

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
        active_snapshot = client.get("/api/runtime/debug").json()
        ws.send_json({"type": "client.stop"})
        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    assert summary_payload["type"] == "server.summary"
    assert summary_payload["session_id"] == status_payload["session_id"]
    assert bridge.sent_audio == [b"\x01\x02"]
    assert bridge.sent_images == [b"\xff\xd8\xff"]
    assert bridge.audio_end_calls == 1
    assert bridge.sent_text[-1] == ("Let's work on the first line.", "user")
    assert bridge.closed is True
    assert active_snapshot["active_session_count"] == 1
    assert active_snapshot["active_sessions"][0]["inbound"]["client.audio"] == 1
    assert active_snapshot["active_sessions"][0]["inbound"]["client.video"] == 1
    assert active_snapshot["active_sessions"][0]["inbound"]["client.text"] == 1
    assert active_snapshot["active_sessions"][0]["inbound"]["client.audio_end"] == 1

    post_stop_snapshot = client.get("/api/runtime/debug").json()
    assert post_stop_snapshot["active_session_count"] == 0
    assert post_stop_snapshot["recent_sessions"][0]["session_id"] == status_payload["session_id"]


def test_runtime_debug_includes_pingpong_turn_timings(client: TestClient) -> None:
    FakeBridge.audio_end_events = [
        {
            "type": "server.transcript",
            "role": "user",
            "text": "shoe the donkey",
            "partial": False,
            "turn_id": "user-1",
            "chunk_index": 0,
            "turn_complete": True,
        },
        {
            "type": "server.transcript",
            "role": "assistant",
            "text": "Shoe the Donkey sounds good.",
            "partial": False,
            "turn_id": "assistant-1",
            "chunk_index": 0,
            "turn_complete": False,
        },
        {
            "type": "server.audio",
            "mime": "audio/pcm;rate=24000",
            "data_b64": "AAAA",
            "turn_id": "assistant-1",
            "chunk_index": 1,
            "turn_complete": False,
        },
        {
            "type": "server.text",
            "text": "Shoe the Donkey sounds good. Do you want the first phrase?",
            "turn_id": "assistant-1",
            "chunk_index": 2,
            "turn_complete": True,
        },
    ]

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "client.init", "mode": "music_tutor", "piece": "Shoe the Donkey"})
        status_payload = ws.receive_json()
        ws.send_json({"type": "client.audio", "mime": "audio/pcm;rate=16000", "data_b64": "AA=="})
        ws.send_json({"type": "client.audio_end"})
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"type": "client.stop"})
        ws.receive_json()

    debug_payload = client.get("/api/runtime/debug").json()
    session = debug_payload["recent_sessions"][0]
    turn = session["pingpong"]["recent_turns"][0]
    assert session["session_id"] == status_payload["session_id"]
    assert session["pingpong"]["responded_turn_count"] == 1
    assert session["pingpong"]["completed_turn_count"] == 1
    assert turn["status"] == "completed"
    assert turn["audio_chunk_count"] == 1
    assert turn["user_transcript_final"] == "shoe the donkey"
    assert turn["first_response_ms"] is not None
    assert turn["first_audio_ms"] is not None
    assert turn["full_turn_ms"] is not None


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
