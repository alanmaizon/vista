"""Performance-feedback metrics for Eurydice music analysis."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

from .symbolic import NoteEvent


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _rounded(value: float) -> float:
    return round(_clamp01(value), 3)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = int(round((len(sorted_values) - 1) * _clamp01(pct)))
    return sorted_values[index]


@dataclass(frozen=True)
class PerformanceFeedback:
    """Deterministic quality metrics used by Eurydice lesson flows."""

    pitch_accuracy: float
    rhythm_accuracy: float
    tempo_stability: float
    dynamic_range: float
    articulation_variance: float

    def to_dict(self) -> dict[str, float]:
        return {
            "pitchAccuracy": self.pitch_accuracy,
            "rhythmAccuracy": self.rhythm_accuracy,
            "tempoStability": self.tempo_stability,
            "dynamicRange": self.dynamic_range,
            "articulationVariance": self.articulation_variance,
        }


@dataclass(frozen=True)
class AssessmentConfidence:
    """Confidence metadata for one deterministic assessment pass."""

    overall: float
    audio_capture: float
    alignment: float
    label: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "overall": self.overall,
            "audio_capture": self.audio_capture,
            "alignment": self.alignment,
            "label": self.label,
        }


@dataclass(frozen=True)
class AssessmentItem:
    """Teacher-facing issue surfaced from compare alignment."""

    index: int
    kind: str
    severity: Literal["low", "medium", "high"]
    title: str
    detail: str
    expected_note_name: str | None = None
    played_note_name: str | None = None
    direction: str | None = None
    beat_delta: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "expected_note_name": self.expected_note_name,
            "played_note_name": self.played_note_name,
            "direction": self.direction,
            "beat_delta": self.beat_delta,
        }


@dataclass(frozen=True)
class PerformanceAssessment:
    """Structured tutoring signals derived from deterministic comparison."""

    confidence: AssessmentConfidence
    pitch_errors: tuple[AssessmentItem, ...]
    rhythm_drift: tuple[AssessmentItem, ...]
    hesitation_points: tuple[AssessmentItem, ...]
    articulation_issues: tuple[AssessmentItem, ...]
    strengths: tuple[str, ...]
    focus_areas: tuple[str, ...]
    primary_issue: str | None
    practice_tip: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence.to_dict(),
            "pitch_errors": [item.to_dict() for item in self.pitch_errors],
            "rhythm_drift": [item.to_dict() for item in self.rhythm_drift],
            "hesitation_points": [item.to_dict() for item in self.hesitation_points],
            "articulation_issues": [item.to_dict() for item in self.articulation_issues],
            "strengths": list(self.strengths),
            "focus_areas": list(self.focus_areas),
            "primary_issue": self.primary_issue,
            "practice_tip": self.practice_tip,
        }


InstrumentProfile = Literal["AUTO", "VOICE", "PIANO", "GUITAR", "STRINGS", "WINDS", "PERCUSSION"]


@dataclass(frozen=True)
class PhraseCalibration:
    """Calibration constants applied to phrase-level metric formulas."""

    tempo_cv_scale: float
    dynamic_spread_ref: float
    articulation_cv_ref: float
    rhythm_pitch_weight: float


@dataclass(frozen=True)
class ComparisonCalibration:
    """Calibration constants for expected-vs-played matching strictness."""

    onset_tolerance: float
    duration_tolerance: float
    pitch_match_points: float
    pitch_class_points: float
    onset_points: float
    duration_points: float


_PHRASE_CALIBRATION: dict[str, PhraseCalibration] = {
    "GENERIC": PhraseCalibration(
        tempo_cv_scale=1.6,
        dynamic_spread_ref=0.35,
        articulation_cv_ref=0.75,
        rhythm_pitch_weight=0.45,
    ),
    "VOICE": PhraseCalibration(
        tempo_cv_scale=1.25,
        dynamic_spread_ref=0.28,
        articulation_cv_ref=0.9,
        rhythm_pitch_weight=0.55,
    ),
    "PIANO": PhraseCalibration(
        tempo_cv_scale=1.95,
        dynamic_spread_ref=0.4,
        articulation_cv_ref=0.65,
        rhythm_pitch_weight=0.35,
    ),
    "GUITAR": PhraseCalibration(
        tempo_cv_scale=1.8,
        dynamic_spread_ref=0.38,
        articulation_cv_ref=0.7,
        rhythm_pitch_weight=0.4,
    ),
    "STRINGS": PhraseCalibration(
        tempo_cv_scale=1.5,
        dynamic_spread_ref=0.3,
        articulation_cv_ref=0.82,
        rhythm_pitch_weight=0.5,
    ),
    "WINDS": PhraseCalibration(
        tempo_cv_scale=1.45,
        dynamic_spread_ref=0.32,
        articulation_cv_ref=0.85,
        rhythm_pitch_weight=0.5,
    ),
    "PERCUSSION": PhraseCalibration(
        tempo_cv_scale=2.05,
        dynamic_spread_ref=0.5,
        articulation_cv_ref=0.55,
        rhythm_pitch_weight=0.2,
    ),
}


_COMPARISON_CALIBRATION: dict[str, ComparisonCalibration] = {
    "GENERIC": ComparisonCalibration(
        onset_tolerance=0.12,
        duration_tolerance=0.18,
        pitch_match_points=0.6,
        pitch_class_points=0.35,
        onset_points=0.2,
        duration_points=0.2,
    ),
    "VOICE": ComparisonCalibration(
        onset_tolerance=0.18,
        duration_tolerance=0.24,
        pitch_match_points=0.55,
        pitch_class_points=0.35,
        onset_points=0.2,
        duration_points=0.25,
    ),
    "PIANO": ComparisonCalibration(
        onset_tolerance=0.09,
        duration_tolerance=0.14,
        pitch_match_points=0.65,
        pitch_class_points=0.3,
        onset_points=0.2,
        duration_points=0.15,
    ),
    "GUITAR": ComparisonCalibration(
        onset_tolerance=0.1,
        duration_tolerance=0.16,
        pitch_match_points=0.62,
        pitch_class_points=0.32,
        onset_points=0.2,
        duration_points=0.18,
    ),
    "STRINGS": ComparisonCalibration(
        onset_tolerance=0.13,
        duration_tolerance=0.2,
        pitch_match_points=0.58,
        pitch_class_points=0.34,
        onset_points=0.2,
        duration_points=0.22,
    ),
    "WINDS": ComparisonCalibration(
        onset_tolerance=0.14,
        duration_tolerance=0.2,
        pitch_match_points=0.58,
        pitch_class_points=0.34,
        onset_points=0.2,
        duration_points=0.22,
    ),
    "PERCUSSION": ComparisonCalibration(
        onset_tolerance=0.08,
        duration_tolerance=0.12,
        pitch_match_points=0.4,
        pitch_class_points=0.2,
        onset_points=0.3,
        duration_points=0.3,
    ),
}


def normalize_instrument_profile(profile: str | None) -> str:
    """Normalize an instrument profile string to a supported calibration key."""
    profile_key = (profile or "AUTO").strip().upper()
    if profile_key in {"", "AUTO", "GENERIC"}:
        return "GENERIC"
    if profile_key in _PHRASE_CALIBRATION:
        return profile_key
    return "GENERIC"


def phrase_calibration_for_profile(profile: str | None) -> PhraseCalibration:
    """Return phrase-level calibration constants for the given profile."""
    return _PHRASE_CALIBRATION[normalize_instrument_profile(profile)]


def comparison_calibration_for_profile(profile: str | None) -> ComparisonCalibration:
    """Return compare-level calibration constants for the given profile."""
    return _COMPARISON_CALIBRATION[normalize_instrument_profile(profile)]


class _ComparedEventLike(Protocol):
    pitch_match: bool
    pitch_class_match: bool
    rhythm_match: bool
    onset_match: bool


class _AssessmentComparedEventLike(Protocol):
    index: int
    expected_note_name: str
    expected_duration_code: str
    played_note_name: str | None
    pitch_match: bool
    pitch_class_match: bool
    octave_displacement: int | None
    onset_match: bool
    duration_match: bool
    rhythm_match: bool
    onset_direction: str | None
    onset_delta_ratio: float | None
    onset_delta_beats: float | None
    duration_direction: str | None
    duration_delta_ratio: float | None
    duration_delta_beats: float | None


def _tempo_stability(events: Sequence[NoteEvent], calibration: PhraseCalibration) -> float:
    if len(events) < 3:
        # With fewer than 3 notes, do not overstate tempo confidence.
        return 0.5 if len(events) >= 2 else 0.0
    ioi = [events[index].start_ms - events[index - 1].start_ms for index in range(1, len(events))]
    positive_ioi = [float(value) for value in ioi if value > 0]
    if len(positive_ioi) < 2:
        return 0.0
    mean_ioi = statistics.mean(positive_ioi)
    if mean_ioi <= 0:
        return 0.0
    std_ioi = statistics.pstdev(positive_ioi)
    cv = std_ioi / mean_ioi
    return _rounded(1.0 - min(1.0, cv * calibration.tempo_cv_scale))


def _dynamic_range(samples: Sequence[float], calibration: PhraseCalibration) -> float:
    if not samples:
        return 0.0
    magnitudes = sorted(abs(sample) for sample in samples)
    if not magnitudes:
        return 0.0
    lower = _percentile(magnitudes, 0.15)
    upper = _percentile(magnitudes, 0.95)
    spread = max(0.0, upper - lower)
    # Normalize a robust amplitude spread into [0,1].
    return _rounded(spread / max(0.01, calibration.dynamic_spread_ref))


def _articulation_variance(events: Sequence[NoteEvent], calibration: PhraseCalibration) -> float:
    if len(events) < 2:
        return 0.0
    durations = [float(event.duration_ms) for event in events if event.duration_ms > 0]
    if len(durations) < 2:
        return 0.0
    mean_duration = statistics.mean(durations)
    if mean_duration <= 0:
        return 0.0
    cv = statistics.pstdev(durations) / mean_duration
    # Higher coefficient means more articulation variety.
    return _rounded(min(1.0, cv / max(0.01, calibration.articulation_cv_ref)))


def feedback_from_phrase(
    *,
    samples: Sequence[float],
    notes: Sequence[NoteEvent],
    confidence: float,
    instrument_profile: str | None = None,
) -> PerformanceFeedback:
    """Compute phrase-level performance metrics from detected events and raw audio."""
    calibration = phrase_calibration_for_profile(instrument_profile)
    pitch_accuracy = _rounded(confidence)
    tempo_stability = _tempo_stability(notes, calibration)
    # Rhythm clarity combines tempo regularity and note confidence.
    rhythm_pitch_weight = _clamp01(calibration.rhythm_pitch_weight)
    rhythm_accuracy = _rounded(
        (rhythm_pitch_weight * pitch_accuracy) + ((1.0 - rhythm_pitch_weight) * tempo_stability)
    )
    dynamic_range = _dynamic_range(samples, calibration)
    articulation_variance = _articulation_variance(notes, calibration)
    return PerformanceFeedback(
        pitch_accuracy=pitch_accuracy,
        rhythm_accuracy=rhythm_accuracy,
        tempo_stability=tempo_stability,
        dynamic_range=dynamic_range,
        articulation_variance=articulation_variance,
    )


def feedback_from_comparison(
    comparisons: Sequence[_ComparedEventLike],
    *,
    baseline: PerformanceFeedback | None = None,
    instrument_profile: str | None = None,
) -> PerformanceFeedback:
    """Compute strict lesson-feedback metrics from expected-vs-played comparison rows."""
    # The comparison strictness itself is calibrated in compare.py matching rules.
    # Keep this mapper deterministic while still validating profile values here.
    normalize_instrument_profile(instrument_profile)
    if not comparisons:
        return baseline or PerformanceFeedback(
            pitch_accuracy=0.0,
            rhythm_accuracy=0.0,
            tempo_stability=0.0,
            dynamic_range=0.0,
            articulation_variance=0.0,
        )

    pitch_units = 0.0
    rhythm_units = 0.0
    onset_units = 0.0
    for item in comparisons:
        if item.pitch_match:
            pitch_units += 1.0
        elif item.pitch_class_match:
            pitch_units += 0.5
        if item.rhythm_match:
            rhythm_units += 1.0
        if item.onset_match:
            onset_units += 1.0

    total = float(len(comparisons))
    pitch_accuracy = _rounded(pitch_units / total)
    rhythm_accuracy = _rounded(rhythm_units / total)
    tempo_stability = _rounded(onset_units / total)
    dynamic_range = baseline.dynamic_range if baseline else 0.0
    articulation_variance = baseline.articulation_variance if baseline else 0.0

    return PerformanceFeedback(
        pitch_accuracy=pitch_accuracy,
        rhythm_accuracy=rhythm_accuracy,
        tempo_stability=tempo_stability,
        dynamic_range=_rounded(dynamic_range),
        articulation_variance=_rounded(articulation_variance),
    )


def _confidence_label(score: float) -> str:
    if score >= 0.82:
        return "high"
    if score >= 0.62:
        return "medium"
    return "low"


def _severity_for_magnitude(
    magnitude: float | None,
    *,
    medium_threshold: float,
    high_threshold: float,
) -> Literal["low", "medium", "high"]:
    value = abs(float(magnitude or 0.0))
    if value >= high_threshold:
        return "high"
    if value >= medium_threshold:
        return "medium"
    return "low"


def _dedupe_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _pitch_errors_from_comparison(
    comparisons: Sequence[_AssessmentComparedEventLike],
) -> tuple[AssessmentItem, ...]:
    items: list[AssessmentItem] = []
    for row in comparisons:
        if row.pitch_match:
            continue
        if row.played_note_name is None:
            items.append(
                AssessmentItem(
                    index=row.index,
                    kind="missing_note",
                    severity="high",
                    title=f"Missing note {row.index}",
                    detail=f"Expected {row.expected_note_name}, but I did not hear a stable pitch there.",
                    expected_note_name=row.expected_note_name,
                )
            )
            continue
        if row.pitch_class_match:
            octave_steps = abs(int(row.octave_displacement or 0))
            octave_label = "one octave" if octave_steps == 1 else f"{octave_steps} octaves"
            direction = "high" if (row.octave_displacement or 0) > 0 else "low"
            items.append(
                AssessmentItem(
                    index=row.index,
                    kind="octave_displacement",
                    severity="medium",
                    title=f"Octave slip on note {row.index}",
                    detail=(
                        f"Expected {row.expected_note_name}, heard {row.played_note_name} "
                        f"({octave_label} {direction})."
                    ),
                    expected_note_name=row.expected_note_name,
                    played_note_name=row.played_note_name,
                    direction=direction,
                )
            )
            continue
        items.append(
            AssessmentItem(
                index=row.index,
                kind="pitch_substitution",
                severity="high",
                title=f"Pitch miss on note {row.index}",
                detail=f"Expected {row.expected_note_name}, heard {row.played_note_name}.",
                expected_note_name=row.expected_note_name,
                played_note_name=row.played_note_name,
            )
        )
    return tuple(items)


def _rhythm_drift_from_comparison(
    comparisons: Sequence[_AssessmentComparedEventLike],
) -> tuple[AssessmentItem, ...]:
    items: list[AssessmentItem] = []
    for row in comparisons:
        if row.played_note_name is None or row.rhythm_match:
            continue
        details: list[str] = []
        severity_levels: list[str] = []
        beat_delta: float | None = None
        direction = row.onset_direction

        if not row.onset_match and row.onset_direction:
            onset_severity = _severity_for_magnitude(
                row.onset_delta_beats if row.onset_delta_beats is not None else row.onset_delta_ratio,
                medium_threshold=0.25 if row.onset_delta_beats is not None else 0.12,
                high_threshold=0.5 if row.onset_delta_beats is not None else 0.22,
            )
            severity_levels.append(onset_severity)
            beat_delta = row.onset_delta_beats
            if row.onset_delta_beats is not None:
                details.append(
                    f"Entrance landed about {row.onset_delta_beats:g} beats {row.onset_direction}."
                )
            elif row.onset_delta_ratio is not None:
                details.append(
                    f"Entrance landed {round(row.onset_delta_ratio * 100)}% {row.onset_direction} of the phrase pulse."
                )
            else:
                details.append(f"Entrance landed {row.onset_direction}.")

        if not row.duration_match and row.duration_direction:
            duration_severity = _severity_for_magnitude(
                row.duration_delta_beats if row.duration_delta_beats is not None else row.duration_delta_ratio,
                medium_threshold=0.25 if row.duration_delta_beats is not None else 0.12,
                high_threshold=0.6 if row.duration_delta_beats is not None else 0.22,
            )
            severity_levels.append(duration_severity)
            if row.duration_delta_beats is not None:
                details.append(
                    f"Hold length was about {row.duration_delta_beats:g} beats {row.duration_direction}."
                )
            else:
                details.append(f"Hold length was {row.duration_direction} than written.")

        severity = "low"
        if "high" in severity_levels:
            severity = "high"
        elif "medium" in severity_levels:
            severity = "medium"

        items.append(
            AssessmentItem(
                index=row.index,
                kind="timing_drift",
                severity=severity,
                title=f"Timing drift on note {row.index}",
                detail=" ".join(details) or "Timing drift was detected on this note.",
                expected_note_name=row.expected_note_name,
                played_note_name=row.played_note_name,
                direction=direction,
                beat_delta=beat_delta,
            )
        )
    return tuple(items)


def _hesitation_points_from_phrase(
    comparisons: Sequence[_AssessmentComparedEventLike],
    played_notes: Sequence[NoteEvent],
) -> tuple[AssessmentItem, ...]:
    items_by_index: dict[int, AssessmentItem] = {}
    comparison_by_index = {row.index: row for row in comparisons}

    for row in comparisons:
        if row.played_note_name is None or row.onset_direction != "late":
            continue
        magnitude = row.onset_delta_beats if row.onset_delta_beats is not None else row.onset_delta_ratio
        threshold = 0.35 if row.onset_delta_beats is not None else 0.16
        if float(magnitude or 0.0) < threshold:
            continue
        severity = _severity_for_magnitude(
            magnitude,
            medium_threshold=threshold,
            high_threshold=0.7 if row.onset_delta_beats is not None else 0.28,
        )
        if row.onset_delta_beats is not None:
            detail = f"The phrase hesitated before note {row.index}, landing about {row.onset_delta_beats:g} beats late."
        else:
            detail = f"The phrase hesitated before note {row.index}, stretching the entrance relative to the pulse."
        items_by_index[row.index] = AssessmentItem(
            index=row.index,
            kind="hesitation",
            severity=severity,
            title=f"Hesitation before note {row.index}",
            detail=detail,
            expected_note_name=row.expected_note_name,
            played_note_name=row.played_note_name,
            direction="late",
            beat_delta=row.onset_delta_beats,
        )

    if len(played_notes) < 3:
        return tuple(items_by_index[index] for index in sorted(items_by_index))

    iois = [
        float(played_notes[index].start_ms - played_notes[index - 1].start_ms)
        for index in range(1, len(played_notes))
        if played_notes[index].start_ms > played_notes[index - 1].start_ms
    ]
    if not iois:
        return tuple(items_by_index[index] for index in sorted(items_by_index))

    median_ioi = statistics.median(iois)
    if median_ioi <= 0:
        return tuple(items_by_index[index] for index in sorted(items_by_index))

    for index in range(1, len(played_notes)):
        ioi = float(played_notes[index].start_ms - played_notes[index - 1].start_ms)
        if ioi <= 0:
            continue
        stretch = ioi / median_ioi
        if stretch < 1.6:
            continue
        comparison = comparison_by_index.get(index + 1)
        if comparison is None or (index + 1) in items_by_index:
            continue
        severity = "high" if stretch >= 2.2 else "medium"
        items_by_index[index + 1] = AssessmentItem(
            index=index + 1,
            kind="hesitation",
            severity=severity,
            title=f"Hesitation before note {index + 1}",
            detail=f"The gap into note {index + 1} stretched to {stretch:.1f}x the surrounding pulse.",
            expected_note_name=comparison.expected_note_name,
            played_note_name=comparison.played_note_name,
        )

    return tuple(items_by_index[index] for index in sorted(items_by_index))


def _articulation_issues_from_comparison(
    comparisons: Sequence[_AssessmentComparedEventLike],
) -> tuple[AssessmentItem, ...]:
    items: list[AssessmentItem] = []
    for row in comparisons:
        if row.played_note_name is None or row.duration_match or not row.duration_direction:
            continue
        kind = "overheld" if row.duration_direction == "longer" else "clipped"
        severity = _severity_for_magnitude(
            row.duration_delta_beats if row.duration_delta_beats is not None else row.duration_delta_ratio,
            medium_threshold=0.25 if row.duration_delta_beats is not None else 0.12,
            high_threshold=0.75 if row.duration_delta_beats is not None else 0.24,
        )
        if row.duration_delta_beats is not None:
            detail = (
                f"The {row.expected_duration_code} value was held about {row.duration_delta_beats:g} beats "
                f"{row.duration_direction} than written."
            )
        else:
            detail = f"The {row.expected_duration_code} value was held {row.duration_direction} than written."
        items.append(
            AssessmentItem(
                index=row.index,
                kind=kind,
                severity=severity,
                title=f"Articulation issue on note {row.index}",
                detail=detail,
                expected_note_name=row.expected_note_name,
                played_note_name=row.played_note_name,
                direction=row.duration_direction,
                beat_delta=row.duration_delta_beats,
            )
        )
    return tuple(items)


def _practice_tip_for_issue(primary_issue: str | None, *, confident_take: bool) -> str | None:
    if primary_issue == "pitch placement":
        return "Slow the bar down and anchor each target note before replaying the full phrase."
    if primary_issue == "beat placement":
        return "Count the beat out loud or use a metronome, then replay while keeping each entrance locked to the pulse."
    if primary_issue == "phrase continuity":
        return "Loop the transition into the hesitation point until the phrase keeps moving without a pause."
    if primary_issue == "note length control":
        return "Clap and count the written values first, then replay while releasing each note exactly on time."
    if confident_take:
        return "This bar is ready for one more clean repetition at a slightly faster tempo."
    return "Replay once more with a cleaner take so Eurydice can score it more confidently."


def assessment_from_comparison(
    comparisons: Sequence[_AssessmentComparedEventLike],
    *,
    played_notes: Sequence[NoteEvent],
    audio_confidence: float,
    alignment_accuracy: float,
    baseline: PerformanceFeedback | None = None,
    instrument_profile: str | None = None,
) -> PerformanceAssessment:
    """Build richer teacher-style assessment signals from compare output."""
    normalize_instrument_profile(instrument_profile)

    confidence_score = _rounded((0.75 * float(audio_confidence or 0.0)) + (0.25 * float(alignment_accuracy or 0.0)))
    confidence = AssessmentConfidence(
        overall=confidence_score,
        audio_capture=_rounded(float(audio_confidence or 0.0)),
        alignment=_rounded(float(alignment_accuracy or 0.0)),
        label=_confidence_label(confidence_score),
    )

    pitch_errors = _pitch_errors_from_comparison(comparisons)
    rhythm_drift = _rhythm_drift_from_comparison(comparisons)
    hesitation_points = _hesitation_points_from_phrase(comparisons, played_notes)
    articulation_issues = _articulation_issues_from_comparison(comparisons)

    strengths: list[str] = []
    if confidence.overall >= 0.8:
        strengths.append("The take was clear enough to score with strong confidence.")
    if comparisons and not pitch_errors:
        strengths.append("Pitch placement stayed close to the written notes.")
    if comparisons and not rhythm_drift:
        strengths.append("Beat placement stayed steady across the bar.")
    if len(played_notes) >= 3 and not hesitation_points:
        strengths.append("The phrase kept moving without obvious stalls.")
    if comparisons and not articulation_issues:
        strengths.append("Note lengths tracked the written values cleanly.")
    if baseline and baseline.dynamic_range >= 0.55:
        strengths.append("There was enough dynamic spread to avoid a flat take.")

    focus_areas: list[str] = []
    issue_weights = {
        "pitch placement": sum(3 if item.severity == "high" else 2 if item.severity == "medium" else 1 for item in pitch_errors),
        "beat placement": sum(3 if item.severity == "high" else 2 if item.severity == "medium" else 1 for item in rhythm_drift),
        "phrase continuity": sum(3 if item.severity == "high" else 2 if item.severity == "medium" else 1 for item in hesitation_points),
        "note length control": sum(3 if item.severity == "high" else 2 if item.severity == "medium" else 1 for item in articulation_issues),
    }

    if pitch_errors:
        focus_areas.append("pitch placement")
    if rhythm_drift:
        focus_areas.append("beat placement")
    if hesitation_points:
        focus_areas.append("phrase continuity")
    if articulation_issues:
        focus_areas.append("note length control")

    primary_issue: str | None = None
    best_weight = 0
    for label in ("beat placement", "pitch placement", "phrase continuity", "note length control"):
        weight = issue_weights[label]
        if weight > best_weight:
            primary_issue = label
            best_weight = weight

    return PerformanceAssessment(
        confidence=confidence,
        pitch_errors=pitch_errors,
        rhythm_drift=rhythm_drift,
        hesitation_points=hesitation_points,
        articulation_issues=articulation_issues,
        strengths=_dedupe_strings(strengths),
        focus_areas=_dedupe_strings(focus_areas),
        primary_issue=primary_issue,
        practice_tip=_practice_tip_for_issue(primary_issue, confident_take=confidence.overall >= 0.75 and not focus_areas),
    )
