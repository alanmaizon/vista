from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_runtime_snapshot() -> None:
    response = client.get("/api/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service_name"] == "Ancient Greek Live Tutor"
    assert payload["live_protocol_version"] == "2026-03-15"
    assert "parse_passage" in payload["tools"]


def test_session_bootstrap() -> None:
    response = client.post(
        "/api/live/session",
        json={
            "learner_name": "Alex",
            "mode": "guided_reading",
            "target_text": "logos gar egeneto",
            "microphone_ready": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode_label"] == "Guided Reading"
    assert payload["live_session"]["provider"] == "gemini-live"
    assert payload["live_session"]["protocol_version"] == "2026-03-15"
    assert "client.hello" in payload["live_session"]["accepted_client_events"]
    assert payload["session_state"]["microphone_ready"] is True


def test_live_websocket_scaffold_message() -> None:
    with client.websocket_connect("/ws/live") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "server.ready"
        assert ready["protocol_version"] == "2026-03-15"

        websocket.send_json(
            {
                "type": "client.hello",
                "protocol_version": "2026-03-15",
                "session_id": "session-123",
                "mode": "guided_reading",
                "capabilities": {
                    "audio_input": True,
                    "audio_output": True,
                    "image_input": True,
                    "supports_barge_in": True,
                },
                "client_name": "test-client",
            }
        )

        status = websocket.receive_json()
        assert status["type"] == "server.status"
        assert status["phase"] == "ready"
