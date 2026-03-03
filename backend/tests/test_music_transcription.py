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
from app import music_compare as music_compare_module
from app import music_transcription as music_transcription_module
from app.music_compare import compare_performance_against_score
from app.music_pitch import PitchEstimate, estimate_pitch_fastyin
from app.music_render import build_note_layout, render_music_score, score_to_musicxml
from app.music_symbolic import NoteEvent, SymbolicPhrase, import_simple_score
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
    gap_ms: int | list[int] = 90,
    sample_rate: int = 16000,
) -> bytes:
    if isinstance(gap_ms, int):
        gaps_ms = [gap_ms] * max(0, len(frequencies_hz) - 1)
    else:
        gaps_ms = list(gap_ms)
        if len(gaps_ms) != max(0, len(frequencies_hz) - 1):
            raise ValueError("gap_ms list must have one fewer entries than frequencies_hz.")
    chunks = []
    for index, frequency in enumerate(frequencies_hz):
        chunks.append(synth_tone(frequency, duration_ms=note_duration_ms, sample_rate=sample_rate))
        if index != len(frequencies_hz) - 1:
            gap_samples = int(sample_rate * gaps_ms[index] / 1000)
            gap = b"\x00\x00" * gap_samples
            chunks.append(gap)
    return b"".join(chunks)


def test_transcribe_pcm16_detects_a4() -> None:
    result = transcribe_pcm16(synth_tone(440.0), sample_rate=16000, expected="NOTE")

    assert result.kind == "single_note"
    assert result.notes
    assert result.notes[0].note_name == "A4"
    assert result.confidence > 0.5


def test_estimate_pitch_fastyin_detects_a4() -> None:
    audio_bytes = synth_tone(440.0, duration_ms=700)
    samples = [sample / 32768.0 for (sample,) in struct.iter_unpack("<h", audio_bytes)]

    estimate = estimate_pitch_fastyin(samples, sample_rate=16000)

    assert estimate is not None
    assert estimate.confidence > 0.7
    assert abs(estimate.frequency_hz - 440.0) < 3.0


def test_estimate_pitch_prefers_crepe_when_it_is_more_confident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fastyin(*_args, **_kwargs) -> PitchEstimate:
        return PitchEstimate(frequency_hz=440.0, confidence=0.52)

    def fake_crepe(*_args, **_kwargs) -> PitchEstimate:
        return PitchEstimate(frequency_hz=444.0, confidence=0.81)

    monkeypatch.setattr(music_transcription_module, "estimate_pitch_fastyin", fake_fastyin)
    monkeypatch.setattr(music_transcription_module, "estimate_pitch_crepe", fake_crepe)

    frequency_hz, confidence = music_transcription_module._estimate_pitch([0.0] * 2000, 16000)

    assert abs(frequency_hz - 442.0) < 0.1
    assert abs(confidence - 0.81) < 0.01


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


def build_multimeasure_score() -> music_api_module.MusicScore:
    return music_api_module.MusicScore(
        id=uuid.uuid4(),
        user_id="music-user",
        source_format="NOTE_LINE",
        time_signature="4/4",
        note_count=4,
        normalized="C4/q D4/q | G4/q A4/q",
        summary="Imported 4 notes across 2 measures.",
        warnings=[],
        measures=[
            {
                "index": 1,
                "total_beats": 2.0,
                "notes": [
                    {"note_name": "C4", "midi_note": 60, "duration_code": "q", "beats": 1.0, "token": "C4/q"},
                    {"note_name": "D4", "midi_note": 62, "duration_code": "q", "beats": 1.0, "token": "D4/q"},
                ],
            },
            {
                "index": 2,
                "total_beats": 2.0,
                "notes": [
                    {"note_name": "G4", "midi_note": 67, "duration_code": "q", "beats": 1.0, "token": "G4/q"},
                    {"note_name": "A4", "midi_note": 69, "duration_code": "q", "beats": 1.0, "token": "A4/q"},
                ],
            },
        ],
    )


def test_score_to_musicxml_emits_score_partwise() -> None:
    score = build_stored_score()

    musicxml = score_to_musicxml(score)
    note_layout = build_note_layout(score)
    rendered = render_music_score(score)

    assert "<score-partwise" in musicxml
    assert "<measure number=\"1\">" in musicxml
    assert "<step>C</step>" in musicxml
    assert [anchor["note_name"] for anchor in note_layout] == ["C4", "D4", "E4"]
    assert note_layout[0]["left_pct"] < note_layout[-1]["left_pct"]
    assert rendered.musicxml.startswith("<?xml")
    assert rendered.render_backend in {"VEROVIO", "MUSICXML_FALLBACK"}
    assert len(rendered.note_layout) == 3


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


def test_compare_performance_against_score_detects_octave_displacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    score = build_stored_score()

    def fake_transcribe(*_args, **_kwargs) -> SymbolicPhrase:
        return SymbolicPhrase(
            kind="melody_fragment",
            notes=(
                NoteEvent(
                    midi_note=72,
                    note_name="C5",
                    frequency_hz=523.25,
                    start_ms=0,
                    duration_ms=320,
                    confidence=0.98,
                ),
                NoteEvent(
                    midi_note=62,
                    note_name="D4",
                    frequency_hz=293.66,
                    start_ms=400,
                    duration_ms=320,
                    confidence=0.97,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=800,
                    duration_ms=620,
                    confidence=0.97,
                ),
            ),
            duration_ms=1500,
            confidence=0.97,
            summary="Octave-displaced opening note.",
            warnings=(),
        )

    monkeypatch.setattr(music_compare_module, "transcribe_pcm16", fake_transcribe)

    result = compare_performance_against_score(
        score,
        audio_bytes=b"\x00\x00",
        sample_rate=16000,
    )

    assert result.match is False
    assert result.accuracy > 0.5
    assert result.comparisons[0].pitch_match is False
    assert result.comparisons[0].pitch_class_match is True
    assert result.comparisons[0].octave_displacement == 1
    assert any("same pitch class, one octave high" in mismatch for mismatch in result.mismatches)


def test_compare_performance_against_score_aligns_to_best_phrase_window() -> None:
    score = build_stored_score()
    clip = synth_phrase([220.0, 261.63, 293.66, 329.63, 392.0])  # extra A3 + G4 around the target

    result = compare_performance_against_score(
        score,
        audio_bytes=clip,
        sample_rate=16000,
    )

    assert result.match is True
    assert result.accuracy >= 0.95
    assert not result.mismatches
    assert any("Aligned against notes 2-4 of the take." in warning for warning in result.warnings)
    assert any("Ignored 1 leading extra note" in warning for warning in result.warnings)
    assert any("Ignored 1 trailing extra note" in warning for warning in result.warnings)


def test_compare_performance_against_score_reports_timing_mismatch() -> None:
    score = build_stored_score()
    clip = synth_phrase([261.63, 293.66, 329.63], gap_ms=[420, 90])

    result = compare_performance_against_score(
        score,
        audio_bytes=clip,
        sample_rate=16000,
    )

    assert result.match is False
    assert any("Timing 2:" in mismatch for mismatch in result.mismatches)
    assert result.comparisons[1].pitch_match is True
    assert result.comparisons[1].onset_match is False


def test_compare_performance_against_score_requests_replay_for_low_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    score = build_stored_score()

    def fake_transcribe(*_args, **_kwargs) -> SymbolicPhrase:
        return SymbolicPhrase(
            kind="melody_fragment",
            notes=(
                NoteEvent(
                    midi_note=60,
                    note_name="C4",
                    frequency_hz=261.63,
                    start_ms=0,
                    duration_ms=320,
                    confidence=0.62,
                ),
                NoteEvent(
                    midi_note=62,
                    note_name="D4",
                    frequency_hz=293.66,
                    start_ms=400,
                    duration_ms=320,
                    confidence=0.6,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=800,
                    duration_ms=620,
                    confidence=0.58,
                ),
            ),
            duration_ms=1500,
            confidence=0.61,
            summary="Low-confidence phrase.",
            warnings=(),
        )

    monkeypatch.setattr(music_compare_module, "transcribe_pcm16", fake_transcribe)

    result = compare_performance_against_score(
        score,
        audio_bytes=b"\x00\x00",
        sample_rate=16000,
    )

    assert result.needs_replay is True
    assert result.match is False
    assert "Replay the phrase slowly and clearly" in result.summary
    assert any("Replay requested:" in warning for warning in result.warnings)


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


def test_music_runtime_status_endpoint_reports_verovio_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(music_api_module, "verovio_runtime_status", lambda: (False, "verovio missing"))
    monkeypatch.setattr(music_api_module, "crepe_runtime_status", lambda: (True, "crepe module detected"))

    response = client.get(
        "/api/music/runtime",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "verovio_available": False,
        "verovio_detail": "verovio missing",
        "crepe_available": True,
        "crepe_detail": "crepe module detected",
    }


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
    assert [note["note_name"] for note in body["expected_notes"]] == ["C4", "D4", "E4"]
    assert [anchor["note_name"] for anchor in body["note_layout"]] == ["C4", "D4", "E4"]
    assert body["note_layout"][0]["left_pct"] < body["note_layout"][-1]["left_pct"]


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
    assert body["needs_replay"] is False
    assert body["match"] is False
    assert body["played_phrase"]["notes"]
    assert body["mismatches"]


def test_compare_performance_endpoint_can_scope_to_one_measure(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    stored = build_multimeasure_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        f"/api/music/score/{stored.id}/compare",
        headers={"Authorization": "Bearer test-token"},
        json={
            "audio_b64": base64.b64encode(synth_phrase([392.0, 440.0])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "max_notes": 12,
            "measure_index": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [note["note_name"] for note in body["expected_notes"]] == ["G4", "A4"]
    assert body["match"] is True


def test_guided_lesson_step_returns_first_bar(client: TestClient, fake_music_db: FakeMusicDB) -> None:
    stored = build_multimeasure_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        f"/api/music/score/{stored.id}/lesson-step",
        headers={"Authorization": "Bearer test-token"},
        json={
            "current_measure_index": None,
            "lesson_stage": "idle",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["lesson_complete"] is False
    assert body["lesson_stage"] == "awaiting-compare"
    assert body["measure_index"] == 1
    assert body["note_start_index"] == 0
    assert body["note_end_index"] == 2
    assert "Bar 1: play C4, D4." in body["prompt"]


def test_guided_lesson_step_advances_to_next_bar(client: TestClient, fake_music_db: FakeMusicDB) -> None:
    stored = build_multimeasure_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        f"/api/music/score/{stored.id}/lesson-step",
        headers={"Authorization": "Bearer test-token"},
        json={
            "current_measure_index": 1,
            "lesson_stage": "reviewed",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["lesson_complete"] is False
    assert body["measure_index"] == 2
    assert body["note_start_index"] == 2
    assert body["note_end_index"] == 4
    assert "Bar 2: play G4, A4." in body["prompt"]


def test_guided_lesson_step_marks_completion_on_last_review(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    stored = build_multimeasure_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        f"/api/music/score/{stored.id}/lesson-step",
        headers={"Authorization": "Bearer test-token"},
        json={
            "current_measure_index": 2,
            "lesson_stage": "reviewed",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["lesson_complete"] is True
    assert body["lesson_stage"] == "complete"
    assert body["measure_index"] is None
    assert body["note_start_index"] is None
    assert body["note_end_index"] is None
    assert body["status"] == "Lesson complete."
