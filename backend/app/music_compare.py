"""Performance comparison helpers for Eurydice."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import MusicScore
from .music_transcription import transcribe_pcm16, transcription_to_dict


@dataclass(frozen=True)
class ComparedEvent:
    """Comparison result for one expected note against one played note."""

    index: int
    expected_note_name: str
    expected_duration_code: str
    expected_beats: float
    played_note_name: str | None
    played_duration_ms: int | None
    pitch_match: bool
    rhythm_match: bool


@dataclass(frozen=True)
class PerformanceComparison:
    """Structured comparison payload for a played phrase."""

    match: bool
    accuracy: float
    summary: str
    warnings: tuple[str, ...]
    mismatches: tuple[str, ...]
    expected_notes: tuple[dict, ...]
    played_phrase: dict
    comparisons: tuple[ComparedEvent, ...]


def _flatten_expected_notes(score: MusicScore) -> list[dict]:
    expected_notes: list[dict] = []
    for measure in score.measures or []:
        for note in measure.get("notes", []):
            expected_notes.append(note)
    return expected_notes


def compare_performance_against_score(
    score: MusicScore,
    *,
    audio_bytes: bytes,
    sample_rate: int,
    max_notes: int = 12,
) -> PerformanceComparison:
    """Compare a monophonic played phrase against a stored symbolic score."""
    expected_notes = _flatten_expected_notes(score)
    phrase = transcribe_pcm16(
        audio_bytes,
        sample_rate=sample_rate,
        expected="PHRASE",
        max_notes=max_notes,
    )
    played_notes = list(phrase.notes)
    warnings = list(phrase.warnings)
    mismatches: list[str] = []
    comparisons: list[ComparedEvent] = []

    expected_total_beats = sum(float(note.get("beats", 0.0)) for note in expected_notes) or 1.0
    played_total_ms = sum(note.duration_ms for note in played_notes) or 1
    score_units = 0.0
    total_units = len(expected_notes) or 1

    for index, expected in enumerate(expected_notes):
        played = played_notes[index] if index < len(played_notes) else None
        expected_note_name = str(expected.get("note_name", ""))
        expected_duration_code = str(expected.get("duration_code", ""))
        expected_beats = float(expected.get("beats", 0.0))

        pitch_match = bool(played and played.note_name == expected_note_name)
        rhythm_match = False
        if played:
            expected_ratio = expected_beats / expected_total_beats
            played_ratio = played.duration_ms / played_total_ms
            rhythm_match = abs(expected_ratio - played_ratio) <= 0.22

        comparisons.append(
            ComparedEvent(
                index=index + 1,
                expected_note_name=expected_note_name,
                expected_duration_code=expected_duration_code,
                expected_beats=expected_beats,
                played_note_name=played.note_name if played else None,
                played_duration_ms=played.duration_ms if played else None,
                pitch_match=pitch_match,
                rhythm_match=rhythm_match,
            )
        )

        note_units = 0.0
        if pitch_match:
            note_units += 0.7
        else:
            if played is None:
                mismatches.append(
                    f"Missing note {index + 1}: expected {expected_note_name}."
                )
            else:
                mismatches.append(
                    f"Note {index + 1}: expected {expected_note_name}, heard {played.note_name}."
                )
        if rhythm_match:
            note_units += 0.3
        elif played is not None:
            mismatches.append(
                f"Rhythm {index + 1}: expected about {expected_duration_code}, heard a different length."
            )

        score_units += note_units

    if len(played_notes) > len(expected_notes):
        extra_note_names = ", ".join(note.note_name for note in played_notes[len(expected_notes) :])
        mismatches.append(f"Extra played note{'s' if len(played_notes) - len(expected_notes) != 1 else ''}: {extra_note_names}.")

    accuracy = round(max(0.0, min(1.0, score_units / total_units)), 3)
    match = accuracy >= 0.95 and len(played_notes) == len(expected_notes) and not mismatches

    if not expected_notes:
        warnings.append("The stored score has no notes to compare against.")

    if match:
        summary = (
            f"Matched the target phrase: {' '.join(note['note_name'] for note in expected_notes)} "
            f"with {round(accuracy * 100)}% alignment."
        )
    else:
        summary = (
            f"Heard {' '.join(note.note_name for note in played_notes) or 'no stable notes'}. "
            f"Target was {' '.join(note['note_name'] for note in expected_notes) or 'empty'}. "
            f"Alignment {round(accuracy * 100)}%."
        )

    return PerformanceComparison(
        match=match,
        accuracy=accuracy,
        summary=summary,
        warnings=tuple(dict.fromkeys(warnings)),
        mismatches=tuple(dict.fromkeys(mismatches)),
        expected_notes=tuple(expected_notes),
        played_phrase=transcription_to_dict(phrase),
        comparisons=tuple(comparisons),
    )


def comparison_to_dict(result: PerformanceComparison) -> dict[str, object]:
    """Convert a performance comparison to a JSON-serializable dict."""
    return {
        "match": result.match,
        "accuracy": result.accuracy,
        "summary": result.summary,
        "warnings": list(result.warnings),
        "mismatches": list(result.mismatches),
        "expected_notes": list(result.expected_notes),
        "played_phrase": result.played_phrase,
        "comparisons": [asdict(item) for item in result.comparisons],
    }
