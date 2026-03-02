from __future__ import annotations

import base64
import math
import struct

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("sqlalchemy")
pytest.importorskip("asyncpg")
pytest.importorskip("firebase_admin")
pytest.importorskip("websockets")

from fastapi.testclient import TestClient

from app import auth as auth_module
from app import main as main_module
from app.music_transcription import transcribe_pcm16


def synth_tone(frequency_hz: float, *, duration_ms: int = 900, sample_rate: int = 16000) -> bytes:
    samples = []
    total_samples = int(sample_rate * duration_ms / 1000)
    for index in range(total_samples):
        amplitude = 0.4
        value = math.sin(2 * math.pi * frequency_hz * index / sample_rate) * amplitude
        samples.append(max(-32767, min(32767, int(value * 32767))))
    return b"".join(struct.pack("<h", sample) for sample in samples)


def test_transcribe_pcm16_detects_a4() -> None:
    result = transcribe_pcm16(synth_tone(440.0), sample_rate=16000, expected="NOTE")

    assert result.kind == "single_note"
    assert result.notes
    assert result.notes[0].note_name == "A4"
    assert result.confidence > 0.5


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def fake_init_db() -> None:
        return None

    monkeypatch.setattr(main_module, "init_firebase", lambda: None)
    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "adk_runtime_status", lambda: (False, "test"))
    monkeypatch.setattr(auth_module, "verify_firebase_token", lambda _token: {"uid": "music-user"})

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_music_transcribe_endpoint_returns_symbolic_notes(client: TestClient) -> None:
    payload = {
        "audio_b64": base64.b64encode(synth_tone(440.0)).decode("ascii"),
        "mime": "audio/pcm;rate=16000",
        "expected": "NOTE",
    }

    response = client.post(
        "/api/music/transcribe",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "single_note"
    assert body["notes"][0]["note_name"] == "A4"
