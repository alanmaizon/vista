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


def test_ws_live_forwards_client_text_to_bridge(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal="Coach me on D minor", domain="MUSIC", mode="GUIDED_LESSON")

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "GUIDED_LESSON",
            }
        )
        status_payload = ws.receive_json()
        intro_state = ws.receive_json()

        ws.send_json({"type": "client.text", "text": "Can we work on D minor?"})
        goal_state = ws.receive_json()
        exercise_state = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        complete_state = ws.receive_json()
        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    assert status_payload["type"] == "server.status"
    assert status_payload["skill"] == "GUIDED_LESSON"
    assert intro_state["type"] == "server.lesson_state"
    assert intro_state["phase"] == "intro"
    assert goal_state["phase"] == "goal_capture"
    assert exercise_state["phase"] == "exercise_selection"
    assert complete_state["phase"] == "session_complete"
    assert summary_payload["type"] == "server.summary"
    assert "I am starting a GUIDED_LESSON music tutoring session." in bridge.sent_text[0][0]
    assert bridge.sent_text[0][1] == "user"
    assert bridge.sent_text[-1] == ("Can we work on D minor?", "user")


def test_ws_live_emits_transcript_events_progressively(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeBridge.initial_events = [
        {
            "type": "server.transcript",
            "role": "assistant",
            "text": "Let's begin",
            "partial": True,
        },
        {
            "type": "server.transcript",
            "role": "user",
            "text": "I want help with arpeggios",
            "partial": False,
        },
        {"type": "server.text", "text": "Let's begin with a D minor arpeggio."},
    ]
    session_id = uuid.uuid4()

    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal="Coach me on arpeggios", domain="MUSIC", mode="GUIDED_LESSON")

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "GUIDED_LESSON",
            }
        )
        status_payload = ws.receive_json()
        intro_state = ws.receive_json()
        assistant_partial = ws.receive_json()
        user_transcript = ws.receive_json()
        goal_capture_state = ws.receive_json()
        assistant_text = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        complete_state = ws.receive_json()
        summary_payload = ws.receive_json()

    bridge = FakeBridge.created[0]
    assert status_payload["type"] == "server.status"
    assert intro_state["type"] == "server.lesson_state"
    assert intro_state["phase"] == "intro"
    assert "I am starting a GUIDED_LESSON music tutoring session." in bridge.sent_text[0][0]
    assert assistant_partial == {
        "type": "server.transcript",
        "role": "assistant",
        "text": "Let's begin",
        "partial": True,
    }
    assert user_transcript == {
        "type": "server.transcript",
        "role": "user",
        "text": "I want help with arpeggios",
        "partial": False,
    }
    assert assistant_text == {
        "type": "server.text",
        "text": "Let's begin with a D minor arpeggio.",
    }
    assert goal_capture_state["type"] == "server.lesson_state"
    assert goal_capture_state["phase"] == "goal_capture"
    assert complete_state["type"] == "server.lesson_state"
    assert complete_state["phase"] == "session_complete"
    assert summary_payload["type"] == "server.summary"


def test_ws_guided_session_starts_in_intro_phase(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal=None, domain="MUSIC", mode="GUIDED_LESSON")

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "GUIDED_LESSON",
            }
        )
        ws.receive_json()  # status
        intro_state = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        ws.receive_json()  # session_complete lesson state
        ws.receive_json()  # summary

    assert intro_state["type"] == "server.lesson_state"
    assert intro_state["phase"] == "intro"


def test_ws_guided_goal_capture_transitions_to_exercise_selection(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal=None, domain="MUSIC", mode="GUIDED_LESSON")

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "GUIDED_LESSON",
            }
        )
        ws.receive_json()  # status
        ws.receive_json()  # intro
        ws.send_json({"type": "client.text", "text": "Help me with G major scale."})
        goal_capture = ws.receive_json()
        exercise_selection = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        ws.receive_json()  # session_complete
        ws.receive_json()  # summary

    assert goal_capture["phase"] == "goal_capture"
    assert exercise_selection["phase"] == "exercise_selection"
    assert exercise_selection["captured_goal"] == "Help me with G major scale."


def test_ws_guided_music_analysis_emits_feedback_and_follow_up_transition(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal=None, domain="MUSIC", mode="GUIDED_LESSON")

    async def fake_tool_executor(*_args, **kwargs) -> dict:
        if kwargs.get("tool_name") == "transcribe":
            return {
                "summary": "You rushed the second note; try again with steadier spacing.",
                "confidence": 0.84,
                "notes": [{"note_name": "C4"}, {"note_name": "E4"}, {"note_name": "G4"}],
            }
        return {"ok": True}

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)
    monkeypatch.setattr(main_module, "_execute_live_tool_call", fake_tool_executor)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "GUIDED_LESSON",
            }
        )
        ws.receive_json()  # status
        ws.receive_json()  # intro
        ws.send_json({"type": "client.text", "text": "Help me with C major scale."})
        ws.receive_json()  # goal_capture
        ws.receive_json()  # exercise_selection
        ws.send_json({"type": "client.text", "text": "I played a phrase, was that correct?"})
        listening_state = ws.receive_json()
        lesson_action = ws.receive_json()
        ws.send_json(
            {
                "type": "client.tool",
                "call_id": "transcribe-call",
                "name": "transcribe",
                "args": {"audio_b64": "AA==", "mime": "audio/pcm;rate=16000"},
            }
        )
        tool_result = ws.receive_json()
        analysis_state = ws.receive_json()
        feedback_state = ws.receive_json()
        feedback_card = ws.receive_json()
        ws.send_json({"type": "client.text", "text": "Can you explain that again? I am struggling."})
        follow_up_state = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        ws.receive_json()  # session_complete
        ws.receive_json()  # summary

    assert listening_state["phase"] == "listening"
    assert lesson_action["type"] == "server.lesson_action"
    assert lesson_action["action"] == "capture_phrase"
    assert tool_result["type"] == "server.tool_result"
    assert tool_result["name"] == "transcribe"
    assert analysis_state["phase"] == "analysis"
    assert feedback_state["phase"] == "feedback"
    assert feedback_card["type"] == "server.feedback_card"
    assert "rushed the second note" in feedback_card["card"]["summary"]
    assert follow_up_state["phase"] == "feedback"
    assert follow_up_state["reason"] == "follow_up_question"


def test_ws_guided_music_event_routes_without_duplicate_transition(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid.uuid4()

    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal=None, domain="MUSIC", mode="GUIDED_LESSON")

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)

    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(session_id),
                "mode": "GUIDED_LESSON",
            }
        )
        ws.receive_json()  # status
        ws.receive_json()  # intro
        ws.send_json({"type": "client.text", "text": "Help me with C major."})
        ws.receive_json()  # goal_capture
        ws.receive_json()  # exercise_selection

        ws.send_json(
            {
                "type": "client.text",
                "event_type": "PHRASE_PLAYED",
                "event_payload": {"notes": ["C4", "E4", "G4"]},
            }
        )
        listening_state = ws.receive_json()
        lesson_action = ws.receive_json()

        ws.send_json(
            {
                "type": "client.text",
                "event_type": "PHRASE_PLAYED",
                "event_payload": {"notes": ["C4", "E4", "G4"]},
            }
        )
        ws.send_json({"type": "client.stop"})
        complete_state = ws.receive_json()
        summary = ws.receive_json()

    assert listening_state["type"] == "server.lesson_state"
    assert listening_state["phase"] == "listening"
    assert lesson_action["type"] == "server.lesson_action"
    assert lesson_action["action"] == "capture_phrase"
    assert complete_state["type"] == "server.lesson_state"
    assert complete_state["phase"] == "session_complete"
    assert summary["type"] == "server.summary"


def test_ws_guided_stop_start_recovery_has_single_intro_transition(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_guided_session(*_args, **_kwargs):
        return SimpleNamespace(goal=None, domain="MUSIC", mode="GUIDED_LESSON")

    monkeypatch.setattr(main_module, "_load_owned_session", fake_guided_session)

    first_session = uuid.uuid4()
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(first_session),
                "mode": "GUIDED_LESSON",
            }
        )
        ws.receive_json()  # status
        first_intro = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        first_complete = ws.receive_json()
        ws.receive_json()  # summary

    second_session = uuid.uuid4()
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json(
            {
                "type": "client.init",
                "token": "test-token",
                "session_id": str(second_session),
                "mode": "GUIDED_LESSON",
            }
        )
        ws.receive_json()  # status
        second_intro = ws.receive_json()
        ws.send_json({"type": "client.stop"})
        second_complete = ws.receive_json()
        ws.receive_json()  # summary

    assert first_intro["phase"] == "intro"
    assert first_intro["transition_id"] == 1
    assert first_complete["phase"] == "session_complete"
    assert second_intro["phase"] == "intro"
    assert second_intro["transition_id"] == 1
    assert second_complete["phase"] == "session_complete"


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


def test_classify_tool_error_maps_common_cases() -> None:
    assert main_module._classify_tool_error("Missing required field", status_code=400) == "VALIDATION"
    assert main_module._classify_tool_error("forbidden", status_code=403) == "AUTH"
    assert main_module._classify_tool_error("Not found", status_code=404) == "NOT_FOUND"
    assert main_module._classify_tool_error("timed out waiting for tool response") == "TIMEOUT"
    assert main_module._classify_tool_error("Unexpected", unexpected=True) == "INTERNAL"
