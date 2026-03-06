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
