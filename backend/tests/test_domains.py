from __future__ import annotations

from app.domains.music.runtime import MusicRuntime
from app.domains import build_session_runtime
from app.domains.music.constitution import DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS
from app.music_symbolic import NoteEvent, SymbolicPhrase


def test_build_session_runtime_returns_music_runtime() -> None:
    runtime = build_session_runtime(domain="music", skill="NOT_A_REAL_MUSIC_SKILL", goal="Identify this phrase")

    assert runtime.domain == "MUSIC"
    assert runtime.skill == "HEAR_PHRASE"
    assert runtime.system_prompt("vision", DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS) == DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS


def test_build_session_runtime_defaults_to_vision() -> None:
    runtime = build_session_runtime(domain="unknown-domain", skill="READ_TEXT", goal="Read the page")

    assert runtime.domain == "VISION"
    assert runtime.skill == "READ_TEXT"


def test_music_runtime_uses_local_phrase_analysis_on_confirm(
    monkeypatch,
) -> None:
    runtime = MusicRuntime(skill="HEAR_PHRASE", goal="Identify this minor arpeggio")

    def fake_transcribe(*_args, **_kwargs) -> SymbolicPhrase:
        return SymbolicPhrase(
            kind="arpeggio_candidate",
            notes=(
                NoteEvent(
                    midi_note=57,
                    note_name="A3",
                    frequency_hz=220.0,
                    start_ms=0,
                    duration_ms=280,
                    confidence=0.88,
                ),
                NoteEvent(
                    midi_note=60,
                    note_name="C4",
                    frequency_hz=261.63,
                    start_ms=320,
                    duration_ms=280,
                    confidence=0.87,
                ),
                NoteEvent(
                    midi_note=64,
                    note_name="E4",
                    frequency_hz=329.63,
                    start_ms=640,
                    duration_ms=280,
                    confidence=0.87,
                ),
                NoteEvent(
                    midi_note=69,
                    note_name="A4",
                    frequency_hz=440.0,
                    start_ms=960,
                    duration_ms=320,
                    confidence=0.86,
                ),
            ),
            duration_ms=1400,
            confidence=0.87,
            harmony_hint="Likely A minor harmony.",
            summary="Detected 4 notes: A3, C4, E4, A4.",
            warnings=(),
        )

    monkeypatch.setattr("app.domains.music.runtime.transcribe_pcm16", fake_transcribe)

    runtime.on_client_audio(b"\x00\x01" * 12000, "audio/pcm;rate=16000")
    assert runtime.on_client_confirm() is None
    events = runtime.on_client_confirm_events()

    assert events
    assert events[0]["type"] == "server.text"
    assert "A3, C4, E4, A4" in events[0]["text"]
    assert "arpeggio outlining A minor" in events[0]["text"]
    assert runtime.completed is True


def test_music_runtime_requests_replay_when_live_phrase_is_too_short() -> None:
    runtime = MusicRuntime(skill="HEAR_PHRASE", goal="Identify this phrase")

    runtime.on_client_audio(b"\x00\x01" * 1000, "audio/pcm;rate=16000")
    assert runtime.on_client_confirm() is None
    events = runtime.on_client_confirm_events()

    assert events
    assert "Play the full phrase once" in events[0]["text"]
    assert runtime.completed is False
