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

pytestmark = pytest.mark.skip(reason="Legacy music HTTP backend retired in the live-agent reset.")

from fastapi.testclient import TestClient

from app import auth as auth_module
from app import db as db_module
from app import main as main_module
from app.domains.music import api as music_api_module
from app.domains.music import compare as music_compare_module
from app.domains.music import transcription as music_transcription_module
from app.domains.music.compare import compare_performance_against_score
from app.domains.music.feedback import comparison_calibration_for_profile
from app.domains.music.models import (
    MusicChallengeAttempt,
    MusicCollaborationSession,
    MusicEngagementProfile,
    MusicLibraryItem,
    MusicLiveAudioTrace,
    MusicLessonAssignment,
    MusicLessonPack,
    MusicLessonPackEntry,
    MusicPerformanceAttempt,
    MusicScore,
    MusicSkillProfile,
)
from app.domains.music.pitch import PitchEstimate, estimate_pitch_fastyin
from app.domains.music.render import build_note_layout, render_music_score, score_to_musicxml
from app.domains.music.symbolic import NoteEvent, SymbolicPhrase, import_simple_score
from app.domains.music.transcription import transcribe_pcm16


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


def test_transcribe_pcm16_stepped_sine_detects_three_notes() -> None:
    """A stepped sine wave (C4, E4, G4) should yield three distinct notes."""
    clip = synth_phrase([261.63, 329.63, 392.00], note_duration_ms=400, gap_ms=120)
    result = transcribe_pcm16(clip, sample_rate=16000, max_notes=8)

    assert len(result.notes) == 3
    detected_names = [n.note_name for n in result.notes]
    assert detected_names == ["C4", "E4", "G4"]
    assert result.confidence > 0.4


def test_tempo_detection_from_even_phrase() -> None:
    """Three evenly-spaced notes at ~500ms IOI should yield ~120 BPM."""
    clip = synth_phrase(
        [261.63, 329.63, 392.00],
        note_duration_ms=400,
        gap_ms=100,
    )
    result = transcribe_pcm16(clip, sample_rate=16000, max_notes=8)

    assert len(result.notes) >= 2
    assert result.tempo_bpm is not None
    # At 400ms note + 100ms gap = 500ms IOI → 120 BPM (within tolerance)
    assert 80 < result.tempo_bpm < 200


def test_single_note_has_no_tempo() -> None:
    """A single note cannot produce a meaningful tempo estimate."""
    result = transcribe_pcm16(synth_tone(440.0), sample_rate=16000, expected="NOTE")

    assert result.tempo_bpm is None
    assert result.notes[0].beats is None


def test_notes_have_beats_when_tempo_detected() -> None:
    """When tempo is detected, each note should carry a beats value."""
    clip = synth_phrase(
        [261.63, 329.63, 392.00],
        note_duration_ms=400,
        gap_ms=100,
    )
    result = transcribe_pcm16(clip, sample_rate=16000, max_notes=8)

    assert result.tempo_bpm is not None
    for note in result.notes:
        assert note.beats is not None
        assert note.beats > 0


def test_transcription_to_dict_includes_tempo() -> None:
    """transcription_to_dict should serialize tempo_bpm and beats."""
    from app.domains.music.transcription import transcription_to_dict

    clip = synth_phrase(
        [261.63, 329.63, 392.00],
        note_duration_ms=400,
        gap_ms=100,
    )
    result = transcribe_pcm16(clip, sample_rate=16000, max_notes=8)
    d = transcription_to_dict(result)

    assert "tempo_bpm" in d
    assert d["tempo_bpm"] == result.tempo_bpm
    assert "performance_feedback" in d
    assert set(d["performance_feedback"]) == {
        "pitchAccuracy",
        "rhythmAccuracy",
        "tempoStability",
        "dynamicRange",
        "articulationVariance",
    }
    assert 0.0 <= d["performance_feedback"]["pitchAccuracy"] <= 1.0
    for note_dict in d["notes"]:
        assert "beats" in note_dict


def test_transcribe_feedback_changes_with_instrument_profile() -> None:
    clip = synth_phrase(
        [261.63, 329.63, 392.0],
        note_duration_ms=360,
        gap_ms=[420, 90],
    )

    voice_result = transcribe_pcm16(
        clip,
        sample_rate=16000,
        max_notes=8,
        instrument_profile="VOICE",
    )
    piano_result = transcribe_pcm16(
        clip,
        sample_rate=16000,
        max_notes=8,
        instrument_profile="PIANO",
    )

    assert voice_result.performance_feedback is not None
    assert piano_result.performance_feedback is not None
    # Voice profile is intentionally more timing-tolerant than piano for this phase.
    assert (
        voice_result.performance_feedback["tempoStability"]
        >= piano_result.performance_feedback["tempoStability"]
    )


def test_compare_calibration_profiles_adjust_tolerances() -> None:
    voice = comparison_calibration_for_profile("VOICE")
    piano = comparison_calibration_for_profile("PIANO")

    assert voice.onset_tolerance > piano.onset_tolerance
    assert voice.duration_tolerance > piano.duration_tolerance


def test_compare_tempo_aware_rhythm_uses_beats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When played phrase has tempo, compare should use beats for duration matching."""
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
                    duration_ms=500,
                    confidence=0.98,
                    beats=1.0,
                ),
                NoteEvent(
                    midi_note=62,
                    note_name="D4",
                    frequency_hz=293.66,
                    start_ms=500,
                    duration_ms=500,
                    confidence=0.97,
                    beats=1.0,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=1000,
                    duration_ms=1000,
                    confidence=0.97,
                    beats=2.0,
                ),
            ),
            duration_ms=2000,
            confidence=0.97,
            summary="Tempo-aware test phrase.",
            warnings=(),
            tempo_bpm=120.0,
        )

    monkeypatch.setattr(music_compare_module, "transcribe_pcm16", fake_transcribe)

    result = compare_performance_against_score(
        score,
        audio_bytes=b"\x00\x00",
        sample_rate=16000,
    )

    assert result.match is True
    assert result.accuracy >= 0.95


def test_compare_builds_structured_assessment(
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
                    duration_ms=420,
                    confidence=0.98,
                    beats=0.84,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=1000,
                    duration_ms=80,
                    confidence=0.77,
                    beats=0.16,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=1500,
                    duration_ms=700,
                    confidence=0.83,
                    beats=1.4,
                ),
            ),
            duration_ms=2200,
            confidence=0.86,
            summary="Structured assessment test phrase.",
            warnings=(),
            tempo_bpm=120.0,
            performance_feedback={
                "pitchAccuracy": 0.86,
                "rhythmAccuracy": 0.71,
                "tempoStability": 0.68,
                "dynamicRange": 0.61,
                "articulationVariance": 0.32,
            },
        )

    monkeypatch.setattr(music_compare_module, "transcribe_pcm16", fake_transcribe)

    result = compare_performance_against_score(
        score,
        audio_bytes=b"\x00\x00",
        sample_rate=16000,
    )

    assessment = result.assessment

    assert assessment["confidence"]["overall"] > 0.65
    assert assessment["confidence"]["label"] in {"medium", "high"}
    assert assessment["pitch_errors"]
    assert assessment["pitch_errors"][0]["kind"] == "pitch_substitution"
    assert any(item["kind"] == "timing_drift" for item in assessment["rhythm_drift"])
    assert any(item["kind"] == "hesitation" for item in assessment["hesitation_points"])
    assert any(item["kind"] == "clipped" for item in assessment["articulation_issues"])
    assert "beat placement" in assessment["focus_areas"]
    assert assessment["practice_tip"]


def test_compare_structured_assessment_stays_clean_on_match(
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
                    duration_ms=500,
                    confidence=0.99,
                    beats=1.0,
                ),
                NoteEvent(
                    midi_note=62,
                    note_name="D4",
                    frequency_hz=293.66,
                    start_ms=500,
                    duration_ms=500,
                    confidence=0.99,
                    beats=1.0,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=1000,
                    duration_ms=1000,
                    confidence=0.99,
                    beats=2.0,
                ),
            ),
            duration_ms=2000,
            confidence=0.97,
            summary="Clean assessment test phrase.",
            warnings=(),
            tempo_bpm=120.0,
            performance_feedback={
                "pitchAccuracy": 0.97,
                "rhythmAccuracy": 0.97,
                "tempoStability": 0.97,
                "dynamicRange": 0.58,
                "articulationVariance": 0.24,
            },
        )

    monkeypatch.setattr(music_compare_module, "transcribe_pcm16", fake_transcribe)

    result = compare_performance_against_score(
        score,
        audio_bytes=b"\x00\x00",
        sample_rate=16000,
    )

    assessment = result.assessment

    assert result.match is True
    assert assessment["pitch_errors"] == []
    assert assessment["rhythm_drift"] == []
    assert assessment["hesitation_points"] == []
    assert assessment["articulation_issues"] == []
    assert assessment["primary_issue"] is None
    assert assessment["practice_tip"]
    assert "Pitch placement stayed close to the written notes." in assessment["strengths"]


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


def build_stored_score() -> MusicScore:
    return MusicScore(
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


def build_multimeasure_score() -> MusicScore:
    return MusicScore(
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
    def __init__(self, scalar=None, scalars=None) -> None:
        self._scalar = scalar
        self._scalars = list(scalars or [])

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        class _Scalars:
            def __init__(self, values):
                self._values = values

            def all(self):
                return list(self._values)

        return _Scalars(self._scalars)


class FakeMusicDB:
    def __init__(self) -> None:
        self.scores = {}
        self.profiles = {}
        self.engagement_profiles = {}
        self.challenge_attempts = {}
        self.attempts = {}
        self.assignments = {}
        self.collaboration_sessions = {}
        self.library_items = {}
        self.lesson_packs = {}
        self.lesson_pack_entries = {}
        self.live_audio_traces = {}
        self._pending = []

    def add(self, instance) -> None:
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        self._pending.append(instance)

    async def commit(self) -> None:
        for pending in self._pending:
            if isinstance(pending, MusicScore):
                self.scores[pending.id] = pending
            elif isinstance(pending, MusicSkillProfile):
                self.profiles[pending.user_id] = pending
            elif isinstance(pending, MusicEngagementProfile):
                self.engagement_profiles[pending.user_id] = pending
            elif isinstance(pending, MusicChallengeAttempt):
                self.challenge_attempts[pending.id] = pending
            elif isinstance(pending, MusicPerformanceAttempt):
                self.attempts[pending.id] = pending
            elif isinstance(pending, MusicLessonAssignment):
                self.assignments[pending.id] = pending
            elif isinstance(pending, MusicCollaborationSession):
                self.collaboration_sessions[pending.id] = pending
            elif isinstance(pending, MusicLibraryItem):
                self.library_items[pending.id] = pending
            elif isinstance(pending, MusicLessonPack):
                self.lesson_packs[pending.id] = pending
            elif isinstance(pending, MusicLessonPackEntry):
                self.lesson_pack_entries[pending.id] = pending
            elif isinstance(pending, MusicLiveAudioTrace):
                self.live_audio_traces[pending.id] = pending
        self._pending = []

    async def refresh(self, instance) -> None:
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    async def execute(self, statement):
        entity = None
        if statement.column_descriptions:
            entity = statement.column_descriptions[0].get("entity")
        whereclause = getattr(statement, "whereclause", None)
        lookup_key = whereclause.right.value if whereclause is not None else None
        if entity is MusicSkillProfile:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.profiles.values())
            return FakeScalarResult(self.profiles.get(lookup_key))
        if entity is MusicEngagementProfile:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.engagement_profiles.values())
            return FakeScalarResult(self.engagement_profiles.get(lookup_key))
        if entity is MusicChallengeAttempt:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.challenge_attempts.values())
            return FakeScalarResult(self.challenge_attempts.get(lookup_key))
        if entity is MusicPerformanceAttempt:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.attempts.values())
            return FakeScalarResult(self.attempts.get(lookup_key))
        if entity is MusicLessonAssignment:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.assignments.values())
            return FakeScalarResult(self.assignments.get(lookup_key))
        if entity is MusicCollaborationSession:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.collaboration_sessions.values())
            return FakeScalarResult(self.collaboration_sessions.get(lookup_key))
        if entity is MusicLibraryItem:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.library_items.values())
            return FakeScalarResult(self.library_items.get(lookup_key))
        if entity is MusicLessonPack:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.lesson_packs.values())
            return FakeScalarResult(self.lesson_packs.get(lookup_key))
        if entity is MusicLessonPackEntry:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.lesson_pack_entries.values())
            return FakeScalarResult(self.lesson_pack_entries.get(lookup_key))
        if entity is MusicLiveAudioTrace:
            if lookup_key is None:
                return FakeScalarResult(scalars=self.live_audio_traces.values())
            filtered = [item for item in self.live_audio_traces.values() if item.user_id == lookup_key]
            return FakeScalarResult(scalars=filtered)
        if lookup_key is None:
            return FakeScalarResult(scalars=self.scores.values())
        return FakeScalarResult(self.scores.get(lookup_key))


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
        "instrument_profile": "VOICE",
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
    assert set(body["performance_feedback"]) == {
        "pitchAccuracy",
        "rhythmAccuracy",
        "tempoStability",
        "dynamicRange",
        "articulationVariance",
    }


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


def test_live_audio_trace_endpoints_persist_and_summarize(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    record_response = client.post(
        "/api/music/analytics/live-audio-trace",
        headers={"Authorization": "Bearer test-token"},
        json={
            "event_type": "PHRASE_PLAYED",
            "router_mode": "MUSIC",
            "speech_active": False,
            "speech_confidence": 0.12,
            "music_confidence": 0.88,
            "pitch_hz": 440.0,
            "pitch_confidence": 0.91,
            "router_summary": {"notes": ["A4", "C5"]},
            "deterministic_summary": {"notes": ["A4", "C5", "E5"], "summary": "A minor arpeggio"},
            "mismatch": True,
            "mismatch_reason": "router_truncated_phrase",
        },
    )

    assert record_response.status_code == 200
    assert record_response.json()["ok"] is True
    assert len(fake_music_db.live_audio_traces) == 1

    metrics_response = client.get(
        "/api/music/analytics/live-audio-trace",
        headers={"Authorization": "Bearer test-token"},
    )

    assert metrics_response.status_code == 200
    body = metrics_response.json()
    assert body["total_traces"] == 1
    assert body["mismatch_count"] == 1
    assert body["mismatch_rate"] == 1.0
    assert body["by_event_type"] == {"PHRASE_PLAYED": 1}
    assert body["recent_traces"][0]["router_summary"]["notes"] == ["A4", "C5"]
    assert body["recent_traces"][0]["deterministic_summary"]["summary"] == "A minor arpeggio"


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


def test_music_score_prepare_endpoint_returns_symbolic_score_and_render(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    response = client.post(
        "/api/music/score/prepare",
        headers={"Authorization": "Bearer test-token"},
        json={
            "source_text": "C4/q D4/q E4/h",
            "source_format": "NOTE_LINE",
            "time_signature": "4/4",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score_id"] is not None
    assert body["normalized"] == "C4/q D4/q E4/h"
    assert body["render_backend"] in {"VEROVIO", "MUSICXML_FALLBACK"}
    assert body["musicxml"].startswith("<?xml")
    assert [note["note_name"] for note in body["expected_notes"]] == ["C4", "D4", "E4"]
    assert [anchor["note_name"] for anchor in body["note_layout"]] == ["C4", "D4", "E4"]

    score_id = uuid.UUID(body["score_id"])
    assert score_id in fake_music_db.scores


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
    assert set(body["performance_feedback"]) == {
        "pitchAccuracy",
        "rhythmAccuracy",
        "tempoStability",
        "dynamicRange",
        "articulationVariance",
    }
    assert 0.0 <= body["performance_feedback"]["pitchAccuracy"] <= 1.0


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


def test_guided_lesson_action_prepares_score_and_returns_first_step(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    response = client.post(
        "/api/music/lesson-action",
        headers={"Authorization": "Bearer test-token"},
        json={
            "source_text": "C4/q D4/q | G4/q A4/q",
            "time_signature": "4/4",
            "lesson_stage": "idle",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "awaiting-compare"
    assert body["score"]["score_id"] is not None
    assert body["score"]["normalized"] == "C4/q D4/q | G4/q A4/q"
    assert body["lesson"]["measure_index"] == 1
    assert body["lesson"]["lesson_complete"] is False

    score_id = uuid.UUID(body["score"]["score_id"])
    assert score_id in fake_music_db.scores


def test_guided_lesson_action_compares_current_bar(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    stored = build_multimeasure_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        "/api/music/lesson-action",
        headers={"Authorization": "Bearer test-token"},
        json={
            "score_id": str(stored.id),
            "current_measure_index": 1,
            "lesson_stage": "awaiting-compare",
            "audio_b64": base64.b64encode(synth_phrase([261.63, 293.66])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "max_notes": 12,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "reviewed"
    assert body["score"] is None
    assert body["lesson"] is None
    assert body["comparison"]["score_id"] == str(stored.id)
    assert body["comparison"]["match"] is True
    assert body["user_skill_profile"]["weakest_dimension"] in {
        "pitch",
        "rhythm",
        "tempo",
        "dynamics",
        "articulation",
    }
    assert isinstance(body["next_drills"], list)
    assert len(body["next_drills"]) >= 2
    assert isinstance(body["tutor_prompt"], str)
    assert "music-user" in fake_music_db.profiles


def test_music_analytics_me_returns_profile_snapshot(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    fake_music_db.profiles["music-user"] = MusicSkillProfile(
        user_id="music-user",
        sample_count=9,
        weakest_dimension="rhythm",
        consistency_score=0.72,
        practice_frequency=0.61,
        last_improvement_trend=0.08,
        overall_score=0.69,
        pitch_score=0.76,
        rhythm_score=0.55,
        tempo_score=0.7,
        dynamics_score=0.66,
        articulation_score=0.64,
    )

    response = client.get(
        "/api/music/analytics/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_profile"] is True
    assert body["weakest_dimension"] == "rhythm"
    assert body["sample_count"] == 9
    assert "pitchAccuracy" in body["rolling_metrics"]


def test_music_analytics_teacher_students_requires_teacher_access(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/music/analytics/teacher/students",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_music_analytics_teacher_students_returns_roster_for_allowed_teacher(
    client: TestClient,
    fake_music_db: FakeMusicDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISTA_TEACHER_UID_ALLOWLIST", "music-user")
    fake_music_db.profiles["student-a"] = MusicSkillProfile(
        user_id="student-a",
        sample_count=12,
        weakest_dimension="pitch",
        consistency_score=0.71,
        practice_frequency=0.64,
        last_improvement_trend=0.03,
        overall_score=0.74,
    )
    fake_music_db.profiles["student-b"] = MusicSkillProfile(
        user_id="student-b",
        sample_count=4,
        weakest_dimension="tempo",
        consistency_score=0.48,
        practice_frequency=0.32,
        last_improvement_trend=-0.06,
        overall_score=0.43,
    )

    response = client.get(
        "/api/music/analytics/teacher/students",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["students"]) == 2
    assert body["students"][0]["user_id"] == "student-a"


def test_compare_endpoint_records_performance_attempt(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    stored = build_stored_score()
    fake_music_db.scores[stored.id] = stored

    response = client.post(
        f"/api/music/score/{stored.id}/compare",
        headers={"Authorization": "Bearer test-token"},
        json={
            "audio_b64": base64.b64encode(synth_phrase([261.63, 293.66, 329.63])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "max_notes": 12,
            "measure_index": 1,
        },
    )

    assert response.status_code == 200
    assert fake_music_db.attempts
    stored_attempt = next(iter(fake_music_db.attempts.values()))
    assert stored_attempt.user_id == "music-user"
    assert stored_attempt.score_id == stored.id
    assert stored_attempt.measure_index == 1


def test_teacher_assignment_create_and_list(
    client: TestClient,
    fake_music_db: FakeMusicDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISTA_TEACHER_UID_ALLOWLIST", "music-user")
    score = build_stored_score()
    fake_music_db.scores[score.id] = score

    create_response = client.post(
        "/api/music/analytics/teacher/assignments",
        headers={"Authorization": "Bearer test-token"},
        json={
            "student_user_id": "student-a",
            "score_id": str(score.id),
            "title": "Bar 1 stability pass",
            "instructions": "Practice at 60 BPM and compare three takes.",
            "target_measures": [1],
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["teacher_user_id"] == "music-user"
    assert created["student_user_id"] == "student-a"

    list_response = client.get(
        "/api/music/analytics/teacher/assignments",
        headers={"Authorization": "Bearer test-token"},
    )

    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body["assignments"]) == 1
    assert body["assignments"][0]["title"] == "Bar 1 stability pass"


def test_teacher_student_detail_returns_attempts_heatmap_and_assignments(
    client: TestClient,
    fake_music_db: FakeMusicDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISTA_TEACHER_UID_ALLOWLIST", "music-user")
    fake_music_db.profiles["student-a"] = MusicSkillProfile(
        user_id="student-a",
        sample_count=6,
        weakest_dimension="rhythm",
        consistency_score=0.63,
        practice_frequency=0.51,
        last_improvement_trend=0.05,
        overall_score=0.67,
        pitch_score=0.72,
        rhythm_score=0.52,
        tempo_score=0.59,
        dynamics_score=0.7,
        articulation_score=0.66,
    )
    attempt_a_id = uuid.uuid4()
    attempt_a = MusicPerformanceAttempt(
        user_id="student-a",
        score_id=uuid.uuid4(),
        measure_index=1,
        instrument_profile="PIANO",
        accuracy=0.81,
        match=True,
        needs_replay=False,
        summary="Matched bar 1 with stable timing.",
        performance_feedback={"pitchAccuracy": 0.84, "rhythmAccuracy": 0.79},
    )
    attempt_a.id = attempt_a_id
    fake_music_db.attempts[attempt_a_id] = attempt_a

    attempt_b_id = uuid.uuid4()
    attempt_b = MusicPerformanceAttempt(
        user_id="student-a",
        score_id=uuid.uuid4(),
        measure_index=1,
        instrument_profile="PIANO",
        accuracy=0.58,
        match=False,
        needs_replay=True,
        summary="Replay requested for bar 1.",
        performance_feedback={"pitchAccuracy": 0.61, "rhythmAccuracy": 0.48},
    )
    attempt_b.id = attempt_b_id
    fake_music_db.attempts[attempt_b_id] = attempt_b

    assignment_id = uuid.uuid4()
    assignment = MusicLessonAssignment(
        teacher_user_id="music-user",
        student_user_id="student-a",
        score_id=None,
        title="Rhythm cleanup",
        instructions="Focus on subdivision consistency.",
        status="ASSIGNED",
        target_measures=[1],
    )
    assignment.id = assignment_id
    fake_music_db.assignments[assignment_id] = assignment

    response = client.get(
        "/api/music/analytics/teacher/students/student-a",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "student-a"
    assert body["profile"]["has_profile"] is True
    assert body["recent_attempts"]
    assert body["measure_heatmap"][0]["measure_index"] == 1
    assert body["assignments"][0]["title"] == "Rhythm cleanup"


def test_library_items_endpoint_filters_by_instrument_difficulty_and_technique(
    client: TestClient,
) -> None:
    create_payloads = [
        {
            "content_type": "EXERCISE",
            "title": "Rhythm Subdivision Drill",
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "technique_tags": ["rhythm", "subdivision"],
            "source_format": "NOTE_LINE",
            "source_text": "C4/q D4/q",
        },
        {
            "content_type": "EXERCISE",
            "title": "Pitch Ladder",
            "instrument": "PIANO",
            "difficulty": "INTERMEDIATE",
            "technique_tags": ["intonation"],
            "source_format": "NOTE_LINE",
            "source_text": "C4/q E4/q",
        },
        {
            "content_type": "THEORY",
            "title": "Guitar Chord Shapes",
            "instrument": "GUITAR",
            "difficulty": "BEGINNER",
            "technique_tags": ["harmony"],
            "source_format": "NOTE_LINE",
            "source_text": "G3/h",
        },
    ]
    for payload in create_payloads:
        created = client.post(
            "/api/music/library/items",
            headers={"Authorization": "Bearer test-token"},
            json=payload,
        )
        assert created.status_code == 200

    filtered = client.get(
        "/api/music/library/items",
        headers={"Authorization": "Bearer test-token"},
        params={
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "technique": "rhythm",
        },
    )

    assert filtered.status_code == 200
    body = filtered.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Rhythm Subdivision Drill"
    assert body["items"][0]["instrument"] == "PIANO"
    assert body["items"][0]["difficulty"] == "BEGINNER"


def test_lesson_pack_load_endpoint_prepares_score_and_guided_lesson(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    first_item = client.post(
        "/api/music/library/items",
        headers={"Authorization": "Bearer test-token"},
        json={
            "content_type": "EXERCISE",
            "title": "Warmup Pattern",
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "technique_tags": ["rhythm"],
            "source_format": "NOTE_LINE",
            "source_text": "C4/q D4/q",
        },
    )
    second_item = client.post(
        "/api/music/library/items",
        headers={"Authorization": "Bearer test-token"},
        json={
            "content_type": "REPERTOIRE",
            "title": "Mini Phrase",
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "technique_tags": ["phrasing"],
            "source_format": "NOTE_LINE",
            "source_text": "E4/q F4/q G4/h",
        },
    )
    assert first_item.status_code == 200
    assert second_item.status_code == 200

    pack = client.post(
        "/api/music/library/packs",
        headers={"Authorization": "Bearer test-token"},
        json={
            "title": "Starter Lesson Pack",
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "item_ids": [
                first_item.json()["item_id"],
                second_item.json()["item_id"],
            ],
            "item_expected_outcomes": [
                "Steady quarter note pulse.",
                "Shape a simple three-note phrase.",
            ],
        },
    )
    assert pack.status_code == 200
    pack_body = pack.json()
    assert len(pack_body["entries"]) == 2

    loaded = client.post(
        f"/api/music/library/packs/{pack_body['pack_id']}/load",
        headers={"Authorization": "Bearer test-token"},
        json={"entry_index": 2, "time_signature": "4/4"},
    )

    assert loaded.status_code == 200
    body = loaded.json()
    assert body["selected_item_id"] == second_item.json()["item_id"]
    assert body["score"]["normalized"] == "E4/q F4/q G4/h"
    assert body["lesson"]["measure_index"] == 1
    assert body["lesson"]["lesson_complete"] is False

    score_id = uuid.UUID(body["score"]["score_id"])
    assert score_id in fake_music_db.scores
    assert fake_music_db.scores[score_id].user_id == "music-user"


def test_library_recommendations_follow_weakest_dimension_tags(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    fake_music_db.profiles["music-user"] = MusicSkillProfile(
        user_id="music-user",
        sample_count=5,
        weakest_dimension="rhythm",
        consistency_score=0.51,
        practice_frequency=0.44,
        last_improvement_trend=0.02,
        overall_score=0.58,
    )
    rhythm_item = client.post(
        "/api/music/library/items",
        headers={"Authorization": "Bearer test-token"},
        json={
            "content_type": "EXERCISE",
            "title": "Rhythm Focus Drill",
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "technique_tags": ["rhythm", "timing"],
            "source_format": "NOTE_LINE",
            "source_text": "C4/q C4/q C4/q C4/q",
            "metadata": {"time_signature": "4/4"},
        },
    )
    pitch_item = client.post(
        "/api/music/library/items",
        headers={"Authorization": "Bearer test-token"},
        json={
            "content_type": "EXERCISE",
            "title": "Pitch Focus Drill",
            "instrument": "PIANO",
            "difficulty": "BEGINNER",
            "technique_tags": ["intonation"],
            "source_format": "NOTE_LINE",
            "source_text": "C4/q E4/q G4/q",
        },
    )
    assert rhythm_item.status_code == 200
    assert pitch_item.status_code == 200

    recommended = client.get(
        "/api/music/library/recommendations/me",
        headers={"Authorization": "Bearer test-token"},
        params={"limit": 3},
    )

    assert recommended.status_code == 200
    body = recommended.json()
    assert body["focus_dimension"] == "rhythm"
    assert body["items"]
    assert body["items"][0]["item_id"] == rhythm_item.json()["item_id"]
    assert "weakest dimension: rhythm" in body["recommendation_reason"]


def test_engagement_call_response_challenge_updates_streak_and_milestones(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    score = build_stored_score()
    fake_music_db.scores[score.id] = score

    response = client.post(
        "/api/music/engagement/challenges/run",
        headers={"Authorization": "Bearer test-token"},
        json={
            "score_id": str(score.id),
            "mode": "CALL_RESPONSE",
            "audio_b64": base64.b64encode(synth_phrase([261.63, 293.66, 329.63])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "measure_index": 1,
            "max_notes": 12,
            "instrument_profile": "PIANO",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "CALL_RESPONSE"
    assert body["profile"]["total_challenge_attempts"] == 1
    assert body["profile"]["practice_streak_days"] >= 1
    if body["completed"]:
        assert "first-challenge-completed" in body["profile"]["milestones"]
    assert fake_music_db.challenge_attempts
    assert "music-user" in fake_music_db.engagement_profiles


def test_engagement_tempo_ladder_challenge_mode_runs(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    score = build_stored_score()
    fake_music_db.scores[score.id] = score

    response = client.post(
        "/api/music/engagement/challenges/run",
        headers={"Authorization": "Bearer test-token"},
        json={
            "score_id": str(score.id),
            "mode": "TEMPO_LADDER",
            "audio_b64": base64.b64encode(synth_phrase([261.63, 293.66, 329.63])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "measure_index": 1,
            "max_notes": 12,
            "target_tempo_bpm": 146,
            "tempo_tolerance_bpm": 25,
            "instrument_profile": "PIANO",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "TEMPO_LADDER"
    assert body["comparison"]["score_id"] == str(score.id)
    assert body["accuracy"] >= 0.0


def test_engagement_telemetry_reports_completion_rates(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    score = build_stored_score()
    fake_music_db.scores[score.id] = score

    client.post(
        "/api/music/engagement/challenges/run",
        headers={"Authorization": "Bearer test-token"},
        json={
            "score_id": str(score.id),
            "mode": "CALL_RESPONSE",
            "audio_b64": base64.b64encode(synth_phrase([261.63, 293.66, 329.63])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "measure_index": 1,
            "max_notes": 12,
        },
    )
    client.post(
        "/api/music/engagement/challenges/run",
        headers={"Authorization": "Bearer test-token"},
        json={
            "score_id": str(score.id),
            "mode": "CALL_RESPONSE",
            "audio_b64": base64.b64encode(synth_phrase([261.63, 311.13, 329.63])).decode("ascii"),
            "mime": "audio/pcm;rate=16000",
            "measure_index": 1,
            "max_notes": 12,
        },
    )

    telemetry = client.get(
        "/api/music/engagement/telemetry",
        headers={"Authorization": "Bearer test-token"},
    )

    assert telemetry.status_code == 200
    body = telemetry.json()
    assert body["total_attempts"] == 2
    assert body["by_mode"]
    call_response = next(item for item in body["by_mode"] if item["mode"] == "CALL_RESPONSE")
    assert call_response["attempts"] == 2
    assert 0.0 <= call_response["completion_rate"] <= 1.0


def test_collaboration_session_syncs_active_measure_and_phrase(
    client: TestClient,
    fake_music_db: FakeMusicDB,
) -> None:
    score = build_stored_score()
    fake_music_db.scores[score.id] = score

    created = client.post(
        "/api/music/engagement/collaboration/sessions",
        headers={"Authorization": "Bearer test-token"},
        json={
            "score_id": str(score.id),
            "active_measure_index": 1,
            "target_phrase": "C4 D4 E4",
        },
    )

    assert created.status_code == 200
    session_id = created.json()["session_id"]

    synced = client.post(
        f"/api/music/engagement/collaboration/sessions/{session_id}/sync",
        headers={"Authorization": "Bearer test-token"},
        json={
            "active_measure_index": 2,
            "target_phrase": "G4 A4",
            "status": "PAUSED",
        },
    )

    assert synced.status_code == 200
    sync_body = synced.json()
    assert sync_body["active_measure_index"] == 2
    assert sync_body["target_phrase"] == "G4 A4"
    assert sync_body["status"] == "PAUSED"

    fetched = client.get(
        f"/api/music/engagement/collaboration/sessions/{session_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["active_measure_index"] == 2
