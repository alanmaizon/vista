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
    assert payload["session_state"]["microphone_ready"] is True


def test_live_websocket_scaffold_message() -> None:
    with client.websocket_connect("/ws/live") as websocket:
        payload = websocket.receive_json()
        assert payload["type"] == "server.status"
        assert payload["status"] == "scaffold"
