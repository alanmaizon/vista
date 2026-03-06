from __future__ import annotations

from app.domains.music.constitution import DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS
from app.domains.music.prompt_eval import evaluate_prompt_quality


def test_default_music_prompt_passes_core_quality_checks() -> None:
    report = evaluate_prompt_quality(DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS)

    assert report["score"] == 1.0
    assert report["passed"] == report["total"]


def test_prompt_quality_flags_missing_core_requirements() -> None:
    report = evaluate_prompt_quality("You are a music helper.")

    assert report["score"] < 1.0
    failed = [check for check in report["checks"] if not check["passed"]]
    assert failed

