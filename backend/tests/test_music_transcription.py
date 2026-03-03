from __future__ import annotations

import base64
import math
import struct
import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("sqlalchemy")
pytest.importorskip("asyncpg")
pytest.importorskip("firebase_admin")
pytest.importorskip("websockets")

from fastapi.testclient import TestClient

from app import auth as auth_module
from app import db as db_module
from app import main as main_module
from app import music_api as music_api_module
from app.music_compare import compare_performance_against_score
from app.music_render import render_music_score, score_to_musicxml
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


def synth_phrase(
    frequencies_hz: list[float],
    *,
    note_duration_ms: int = 320,
    gap_ms: int = 90,
    sample_rate: int = 16000,
) -> bytes:
    gap_samples = int(sample_rate * gap_ms / 1000)
    gap = b"\x00\x00" * gap_samples
    chunks = []
    for index, frequency in enumerate(frequencies_hz):
        chunks.append(synth_tone(frequency, duration_ms=note_duration_ms, sample_rate=sample_rate))
        if index != len(frequencies_hz) - 1:
            chunks.append(gap)
    return b"".join(chunks)


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


def build_stored_score() -> music_api_module.MusicScore:
    return music_api_module.MusicScore(
        id=uuid.uuid4(),
        user_id="music-user",
        source_format="NOTE_LINE",
        time_signature="4/4",
        note_count=3,
        normalized="C4/q D4/q E4/h",
        summary="Imported 3 notes across 1 measure.",
        warnings=[],
        measures=[
            {
                "index": 1,
                "total_beats": 4.0,
                "notes": [
                    {"note_name": "C4", "midi_note": 60, "duration_code": "q", "beats": 1.0, "token": "C4/q"},
                    {"note_name": "D4", "midi_note": 62, "duration_code": "q", "beats": 1.0, "token": "D4/q"},
                    {"note_name": "E4", "midi_note": 64, "duration_code": "h", "beats": 2.0, "token": "E4/h"},
                ],
            }
        ],
    )


def test_score_to_musicxml_emits_score_partwise() -> None:
    score = build_stored_score()

    musicxml = score_to_musicxml(score)
    rendered = render_music_score(score)

    assert "<score-partwise" in musicxml
    assert "<measure number=\"1\">" in musicxml
    assert "<step>C</step>" in musicxml
    assert rendered.musicxml.startswith("<?xml")
    assert rendered.render_backend in {"VEROVIO", "MUSICXML_FALLBACK"}


def test_compare_performance_against_score_detects_exact_match() -> None:
    score = build_stored_score()
    clip = synth_phrase([261.63, 293.66, 329.63])

    result = compare_performance_against_score(
        score,
        audio_bytes=clip,
        sample_rate=16000,
    )

    assert result.match is True
    assert result.accuracy >= 0.95
    assert not result.mismatches


def test_compare_performance_against_score_reports_pitch_mismatch() -> None:
    score = build_stored_score()
    clip = synth_phrase([261.63, 311.13, 329.63])  # C4, D#4, E4

    result = compare_performance_against_score(
        score,
        audio_bytes=clip,
        sample_rate=16000,
    )

    assert result.match is False
    assert any("expected D4, heard D#4" in mismatch for mismatch in result.mismatches)


class FakeScalarResult:
    def __init__(self, scalar=None) -> None:
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class FakeMusicDB:
    def __init__(self) -> None:
        self.scores = {}

    def add(self, instance) -> None:
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        self._pending = instance

    async def commit(self) -> None:
        pending = getattr(self, "_pending", None)
        if pending is not None:
            self.scores[pending.id] = pending

    async def refresh(self, instance) -> None:
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    async def execute(self, statement):
        score_id = statement.whereclause.right.value
        return FakeScalarResult(self.scores.get(score_id))


@pytest.fixture
def fake_music_db() -> FakeMusicDB:
    return FakeMusicDB()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, fake_music_db: FakeMusicDB) -> TestClient:
    async def fake_init_db() -> None:
        return None

    async def fake_get_db():
        yield fake_music_db

    monkeypatch.setattr(main_module, "init_firebase", lambda: None)
    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "adk_runtime_status", lambda: (False, "test"))
    monkeypatch.setattr(auth_module, "verify_firebase_token", lambda _token: {"uid": "music-user"})

    main_module.app.dependency_overrides[db_module.get_db] = fake_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


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


def test_music_score_import_endpoint_returns_symbolic_score(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
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
    assert body["score_id"] is not None
    assert body["normalized"] == "C4/q D4/q E4/h | G4/q A4/q B4/h"
    assert len(body["measures"]) == 2
    assert body["measures"][0]["notes"][0]["note_name"] == "C4"

    score_id = uuid.UUID(body["score_id"])
    stored = fake_music_db.scores[score_id]
    assert stored.user_id == "music-user"
    assert stored.time_signature == "4/4"


def test_get_music_score_endpoint_returns_owned_score(client: TestClient, fake_music_db: FakeMusicDB) -> None:
    stored = build_stored_score()
    fake_music_db.scores[stored.id] = stored

    response = client.get(
        f"/api/music/score/{stored.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score_id"] == str(stored.id)
    assert body["normalized"] == "C4/q D4/q E4/h"


def test_render_music_score_endpoint_returns_musicxml(client: TestClient, fake_music_db: FakeMusicDB) -> None:
    stored = build_stored_score()
    fake_music_db.scores[stored.id] = stored

    response = client.get(
        f"/api/music/score/{stored.id}/render",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score_id"] == str(stored.id)
    assert body["render_backend"] in {"VEROVIO", "MUSICXML_FALLBACK"}
    assert body["musicxml"].startswith("<?xml")


def test_compare_performance_endpoint_returns_alignment_feedback(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    stored = build_stored_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        f"/api/music/score/{stored.id}/compare",
        headers={"Authorization": "Bearer test-token"},
        json={
            "audio_b64": base64.b64encode(synth_phrase([261.63, 311.13, 329.63])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "max_notes": 12,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score_id"] == str(stored.id)
    assert body["match"] is False
    assert body["played_phrase"]["notes"]
    assert body["mismatches"]
