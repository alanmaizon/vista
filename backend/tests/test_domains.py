from __future__ import annotations

from app.domains import build_session_runtime
from app.domains.music.constitution import DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS


def test_build_session_runtime_returns_music_runtime() -> None:
    runtime = build_session_runtime(domain="music", skill="NOT_A_REAL_MUSIC_SKILL", goal="Identify this phrase")

    assert runtime.domain == "MUSIC"
    assert runtime.skill == "HEAR_PHRASE"
    assert runtime.system_prompt("vision", DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS) == DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS


def test_build_session_runtime_defaults_to_vision() -> None:
    runtime = build_session_runtime(domain="unknown-domain", skill="READ_TEXT", goal="Read the page")

    assert runtime.domain == "VISION"
    assert runtime.skill == "READ_TEXT"
