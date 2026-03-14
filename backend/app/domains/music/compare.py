"""Performance comparison helpers for Eurydice."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .feedback import (
    ComparisonCalibration,
    PerformanceFeedback,
    assessment_from_comparison,
    comparison_calibration_for_profile,
    feedback_from_comparison,
)
from .symbolic import note_name_to_midi
from .transcription import transcribe_pcm16, transcription_to_dict
from .models import MusicScore

REPLAY_CONFIDENCE_THRESHOLD = 0.72


@dataclass(frozen=True)
class ComparedEvent:
    """Comparison result for one expected note against one played note."""

    index: int
    expected_note_name: str
    expected_duration_code: str
    expected_beats: float
    expected_start_beat: float
    played_note_name: str | None
    played_start_ms: int | None
    played_duration_ms: int | None
    played_confidence: float | None
    played_start_beat: float | None
    pitch_match: bool
    pitch_class_match: bool
    octave_displacement: int | None
    onset_match: bool
    onset_direction: str | None
    onset_delta_ratio: float | None
    onset_delta_beats: float | None
    duration_match: bool
    duration_direction: str | None
    duration_delta_ratio: float | None
    duration_delta_beats: float | None
    rhythm_match: bool


@dataclass(frozen=True)
class PerformanceComparison:
    """Structured comparison payload for a played phrase."""

    needs_replay: bool
    match: bool
    accuracy: float
    summary: str
    warnings: tuple[str, ...]
    mismatches: tuple[str, ...]
    expected_notes: tuple[dict, ...]
    played_phrase: dict
    comparisons: tuple[ComparedEvent, ...]
    performance_feedback: dict[str, float]
    assessment: dict[str, object]


def _flatten_expected_notes(score: MusicScore) -> list[dict]:
    expected_notes: list[dict] = []
    for measure in score.measures or []:
        for note in measure.get("notes", []):
            expected_notes.append(note)
    return expected_notes


def _compare_expected_window(
    expected_notes: list[dict],
    played_window: list,
    *,
    calibration: ComparisonCalibration,
    played_tempo_bpm: float | None = None,
) -> tuple[float, list[str], list[ComparedEvent]]:
    expected_total_beats = sum(float(note.get("beats", 0.0)) for note in expected_notes) or 1.0

    # Prefer beat-based normalization when played tempo is known
    use_beats = played_tempo_bpm is not None and all(
        getattr(n, "beats", None) is not None for n in played_window
    )
    beat_ms = (60000.0 / played_tempo_bpm) if use_beats and played_tempo_bpm else None
    if use_beats:
        played_total_beats = sum(n.beats for n in played_window) or 1.0
    played_total_ms = sum(note.duration_ms for note in played_window) or 1

    expected_onset_span_beats = sum(float(note.get("beats", 0.0)) for note in expected_notes[:-1]) or 1.0
    played_window_start_ms = played_window[0].start_ms if played_window else 0
    played_onset_span_ms = (
        max(1, played_window[-1].start_ms - played_window_start_ms)
        if len(played_window) > 1
        else 1
    )
    score_units = 0.0
    mismatches: list[str] = []
    comparisons: list[ComparedEvent] = []
    expected_start_beat = 0.0

    for index, expected in enumerate(expected_notes):
        played = played_window[index] if index < len(played_window) else None
        expected_note_name = str(expected.get("note_name", ""))
        expected_duration_code = str(expected.get("duration_code", ""))
        expected_beats = float(expected.get("beats", 0.0))

        pitch_match = bool(played and played.note_name == expected_note_name)
        pitch_class_match = False
        octave_displacement: int | None = None
        if played and not pitch_match:
            expected_midi = note_name_to_midi(expected_note_name)
            played_midi = note_name_to_midi(played.note_name)
            pitch_class_match = expected_midi % 12 == played_midi % 12
            if pitch_class_match:
                octave_displacement = (played_midi - expected_midi) // 12
        onset_match = False
        duration_match = False
        rhythm_match = False
        played_start_beat: float | None = None
        onset_direction: str | None = None
        onset_delta_ratio: float | None = None
        onset_delta_beats: float | None = None
        duration_direction: str | None = None
        duration_delta_ratio: float | None = None
        duration_delta_beats: float | None = None
        if played:
            expected_duration_ratio = expected_beats / expected_total_beats
            if use_beats:
                played_duration_ratio = played.beats / played_total_beats
            else:
                played_duration_ratio = played.duration_ms / played_total_ms
            signed_duration_delta = played_duration_ratio - expected_duration_ratio
            duration_delta_ratio = round(abs(signed_duration_delta), 3)
            duration_match = abs(signed_duration_delta) <= calibration.duration_tolerance
            if duration_delta_ratio > 0:
                duration_direction = "longer" if signed_duration_delta > 0 else "shorter"

            expected_onset_ratio = (
                expected_start_beat / expected_onset_span_beats
                if len(expected_notes) > 1
                else 0.0
            )
            played_onset_ratio = (
                (played.start_ms - played_window_start_ms) / played_onset_span_ms
                if len(played_window) > 1
                else 0.0
            )
            signed_onset_delta = played_onset_ratio - expected_onset_ratio
            onset_delta_ratio = round(abs(signed_onset_delta), 3)
            onset_match = abs(signed_onset_delta) <= calibration.onset_tolerance
            if onset_delta_ratio > 0:
                onset_direction = "late" if signed_onset_delta > 0 else "early"

            if beat_ms is not None and beat_ms > 0:
                played_start_beat = round((played.start_ms - played_window_start_ms) / beat_ms, 3)
                onset_delta_beats = round(abs(played_start_beat - expected_start_beat), 3)
                played_duration_beats = played.beats if played.beats is not None else round(played.duration_ms / beat_ms, 3)
                duration_delta_beats = round(abs(float(played_duration_beats) - expected_beats), 3)
            rhythm_match = onset_match and duration_match

        comparisons.append(
            ComparedEvent(
                index=index + 1,
                expected_note_name=expected_note_name,
                expected_duration_code=expected_duration_code,
                expected_beats=expected_beats,
                expected_start_beat=round(expected_start_beat, 3),
                played_note_name=played.note_name if played else None,
                played_start_ms=played.start_ms if played else None,
                played_duration_ms=played.duration_ms if played else None,
                played_confidence=round(float(played.confidence), 3) if played else None,
                played_start_beat=played_start_beat,
                pitch_match=pitch_match,
                pitch_class_match=pitch_class_match,
                octave_displacement=octave_displacement,
                onset_match=onset_match,
                onset_direction=onset_direction,
                onset_delta_ratio=onset_delta_ratio,
                onset_delta_beats=onset_delta_beats,
                duration_match=duration_match,
                duration_direction=duration_direction,
                duration_delta_ratio=duration_delta_ratio,
                duration_delta_beats=duration_delta_beats,
                rhythm_match=rhythm_match,
            )
        )

        note_units = 0.0
        if pitch_match:
            note_units += calibration.pitch_match_points
        elif pitch_class_match:
            note_units += calibration.pitch_class_points
            if played is not None:
                octave_steps = abs(octave_displacement or 0)
                octave_count = "one octave" if octave_steps == 1 else f"{octave_steps} octaves"
                direction = "high" if (octave_displacement or 0) > 0 else "low"
                mismatches.append(
                    f"Note {index + 1}: expected {expected_note_name}, heard {played.note_name} "
                    f"(same pitch class, {octave_count} {direction})."
                )
        else:
            if played is None:
                mismatches.append(
                    f"Missing note {index + 1}: expected {expected_note_name}."
                )
            else:
                mismatches.append(
                    f"Note {index + 1}: expected {expected_note_name}, heard {played.note_name}."
                )

        if onset_match:
            note_units += calibration.onset_points
        elif played is not None:
            direction = "late" if played.start_ms > played_window_start_ms else "early"
            if len(played_window) > 1:
                expected_onset_ratio = (
                    expected_start_beat / expected_onset_span_beats
                    if len(expected_notes) > 1
                    else 0.0
                )
                played_onset_ratio = (
                    (played.start_ms - played_window_start_ms) / played_onset_span_ms
                    if len(played_window) > 1
                    else 0.0
                )
                direction = "late" if played_onset_ratio > expected_onset_ratio else "early"
            mismatches.append(
                f"Timing {index + 1}: the note started {direction} for the beat."
            )

        if duration_match:
            note_units += calibration.duration_points
        elif played is not None:
            expected_duration_ratio = expected_beats / expected_total_beats
            if use_beats:
                played_duration_ratio = played.beats / played_total_beats
            else:
                played_duration_ratio = played.duration_ms / played_total_ms
            length_direction = duration_direction or (
                "longer" if played_duration_ratio > expected_duration_ratio else "shorter"
            )
            mismatches.append(
                f"Length {index + 1}: expected about {expected_duration_code}, heard a {length_direction} hold."
            )

        score_units += note_units
        expected_start_beat += expected_beats

    return score_units, mismatches, comparisons


def compare_performance_against_score(
    score: MusicScore,
    *,
    audio_bytes: bytes,
    sample_rate: int,
    max_notes: int = 12,
    instrument_profile: str | None = None,
) -> PerformanceComparison:
    """Compare a monophonic played phrase against a stored symbolic score."""
    calibration = comparison_calibration_for_profile(instrument_profile)
    expected_notes = _flatten_expected_notes(score)
    phrase = transcribe_pcm16(
        audio_bytes,
        sample_rate=sample_rate,
        expected="PHRASE",
        max_notes=max_notes,
        instrument_profile=instrument_profile,
    )
    played_notes = list(phrase.notes)
    warnings = list(phrase.warnings)
    mismatches: list[str] = []
    comparisons: list[ComparedEvent] = []
    score_units = 0.0
    total_units = len(expected_notes) or 1
    alignment_start = 0
    played_tempo = phrase.tempo_bpm
    aligned_played_notes = played_notes

    if len(played_notes) > len(expected_notes) and expected_notes:
        best_alignment: tuple[float, int, list[str], list[ComparedEvent]] | None = None
        window_size = len(expected_notes)
        for start in range(0, len(played_notes) - window_size + 1):
            window = played_notes[start : start + window_size]
            candidate_score, candidate_mismatches, candidate_comparisons = _compare_expected_window(
                expected_notes,
                window,
                calibration=calibration,
                played_tempo_bpm=played_tempo,
            )
            ranking = (
                candidate_score,
                -len(candidate_mismatches),
                -start,
            )
            if best_alignment is None:
                best_alignment = (
                    candidate_score,
                    start,
                    candidate_mismatches,
                    candidate_comparisons,
                )
                best_ranking = ranking
                continue
            if ranking > best_ranking:
                best_alignment = (
                    candidate_score,
                    start,
                    candidate_mismatches,
                    candidate_comparisons,
                )
                best_ranking = ranking

        assert best_alignment is not None
        score_units, alignment_start, mismatches, comparisons = best_alignment
        aligned_played_notes = played_notes[
            alignment_start : alignment_start + len(expected_notes)
        ]

        ignored_leading = alignment_start
        ignored_trailing = len(played_notes) - (alignment_start + len(expected_notes))
        if ignored_leading or ignored_trailing:
            warnings.append(
                f"Aligned against notes {alignment_start + 1}-{alignment_start + len(expected_notes)} of the take."
            )
            if ignored_leading:
                ignored_names = ", ".join(
                    note.note_name for note in played_notes[:ignored_leading]
                )
                warnings.append(
                    f"Ignored {ignored_leading} leading extra note{'s' if ignored_leading != 1 else ''}: {ignored_names}."
                )
            if ignored_trailing:
                ignored_names = ", ".join(
                    note.note_name for note in played_notes[-ignored_trailing:]
                )
                warnings.append(
                    f"Ignored {ignored_trailing} trailing extra note{'s' if ignored_trailing != 1 else ''}: {ignored_names}."
                )
    else:
        score_units, mismatches, comparisons = _compare_expected_window(
            expected_notes,
            played_notes,
            calibration=calibration,
            played_tempo_bpm=played_tempo,
        )
        aligned_played_notes = played_notes

    # Warn if played tempo differs significantly from score tempo
    score_tempo = getattr(score, "tempo_bpm", None)
    if played_tempo is not None and score_tempo is not None:
        tempo_ratio = abs(played_tempo - score_tempo) / score_tempo
        if tempo_ratio > 0.20:
            warnings.append(
                "Different tempo detected; rhythm alignment may be less precise."
            )

    accuracy = round(max(0.0, min(1.0, score_units / total_units)), 3)
    needs_replay = phrase.confidence < REPLAY_CONFIDENCE_THRESHOLD or not played_notes
    match = accuracy >= 0.95 and bool(expected_notes) and not mismatches and not needs_replay

    if not expected_notes:
        warnings.append("The stored score has no notes to compare against.")

    if needs_replay:
        warnings.append(
            f"Replay requested: this take was only {round(phrase.confidence * 100)}% confident, "
            "so the comparison is provisional."
        )
        if played_notes:
            summary = (
                f"I heard {' '.join(note.note_name for note in played_notes)}, but confidence was only "
                f"{round(phrase.confidence * 100)}%. Replay the phrase slowly and clearly before trusting this comparison."
            )
        else:
            summary = "I could not hear a stable enough phrase to compare. Replay slowly and clearly."
    elif match:
        if alignment_start:
            summary = (
                f"Matched the target phrase after aligning to notes "
                f"{alignment_start + 1}-{alignment_start + len(expected_notes)} of the take. "
                f"Alignment {round(accuracy * 100)}%."
            )
        else:
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

    phrase_feedback = phrase.performance_feedback if isinstance(phrase.performance_feedback, dict) else None
    baseline_feedback = (
        None
        if phrase_feedback is None
        else PerformanceFeedback(
            pitch_accuracy=0.0,
            rhythm_accuracy=0.0,
            tempo_stability=0.0,
            dynamic_range=float(phrase_feedback.get("dynamicRange", 0.0)),
            articulation_variance=float(phrase_feedback.get("articulationVariance", 0.0)),
        )
    )
    performance_feedback = feedback_from_comparison(
        comparisons,
        baseline=baseline_feedback,
        instrument_profile=instrument_profile,
    ).to_dict()
    assessment = assessment_from_comparison(
        comparisons,
        played_notes=aligned_played_notes,
        audio_confidence=phrase.confidence,
        alignment_accuracy=accuracy,
        baseline=baseline_feedback,
        instrument_profile=instrument_profile,
    ).to_dict()

    return PerformanceComparison(
        needs_replay=needs_replay,
        match=match,
        accuracy=accuracy,
        summary=summary,
        warnings=tuple(dict.fromkeys(warnings)),
        mismatches=tuple(dict.fromkeys(mismatches)),
        expected_notes=tuple(expected_notes),
        played_phrase=transcription_to_dict(phrase),
        comparisons=tuple(comparisons),
        performance_feedback=performance_feedback,
        assessment=assessment,
    )


def comparison_to_dict(result: PerformanceComparison) -> dict[str, object]:
    """Convert a performance comparison to a JSON-serializable dict."""
    return {
        "needs_replay": result.needs_replay,
        "match": result.match,
        "accuracy": result.accuracy,
        "summary": result.summary,
        "warnings": list(result.warnings),
        "mismatches": list(result.mismatches),
        "expected_notes": list(result.expected_notes),
        "played_phrase": result.played_phrase,
        "comparisons": [asdict(item) for item in result.comparisons],
        "performance_feedback": result.performance_feedback,
        "assessment": result.assessment,
    }
