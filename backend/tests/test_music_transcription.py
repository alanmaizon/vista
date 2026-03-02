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
from app.music_symbolic import import_simple_score
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


def test_import_simple_score_normalizes_note_line() -> None:
    result = import_simple_score("C4/q D4/q E4/h | G4/q A4/q B4/h")

    assert result.format == "NOTE_LINE"
    assert result.note_count == 6
    assert result.normalized == "C4/q D4/q E4/h | G4/q A4/q B4/h"
    assert len(result.measures) == 2
    assert result.measures[0].notes[0].midi_note == 60
    assert not result.warnings


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


def test_music_score_import_endpoint_returns_symbolic_score(client: TestClient) -> None:
    response = client.post(
        "/api/music/score/import",
        headers={"Authorization": "Bearer test-token"},
        json={
            "source_text": "C4/q D4/q E4/h | G4/q A4/q B4/h",
            "source_format": "NOTE_LINE",
            "time_signature": "4/4",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "NOTE_LINE"
    assert body["note_count"] == 6
    assert body["normalized"] == "C4/q D4/q E4/h | G4/q A4/q B4/h"
    assert len(body["measures"]) == 2
    assert body["measures"][0]["notes"][0]["note_name"] == "C4"
