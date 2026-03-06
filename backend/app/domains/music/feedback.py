"""Performance-feedback metrics for Eurydice music analysis."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Protocol, Sequence

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


class _ComparedEventLike(Protocol):
    pitch_match: bool
    pitch_class_match: bool
    rhythm_match: bool
    onset_match: bool


def _tempo_stability(events: Sequence[NoteEvent]) -> float:
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
    return _rounded(1.0 - min(1.0, cv * 1.6))


def _dynamic_range(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    magnitudes = sorted(abs(sample) for sample in samples)
    if not magnitudes:
        return 0.0
    lower = _percentile(magnitudes, 0.15)
    upper = _percentile(magnitudes, 0.95)
    spread = max(0.0, upper - lower)
    # Normalize a robust amplitude spread into [0,1].
    return _rounded(spread / 0.35)


def _articulation_variance(events: Sequence[NoteEvent]) -> float:
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
    return _rounded(min(1.0, cv / 0.75))


def feedback_from_phrase(*, samples: Sequence[float], notes: Sequence[NoteEvent], confidence: float) -> PerformanceFeedback:
    """Compute phrase-level performance metrics from detected events and raw audio."""
    pitch_accuracy = _rounded(confidence)
    tempo_stability = _tempo_stability(notes)
    # Rhythm clarity combines tempo regularity and note confidence.
    rhythm_accuracy = _rounded((0.45 * pitch_accuracy) + (0.55 * tempo_stability))
    dynamic_range = _dynamic_range(samples)
    articulation_variance = _articulation_variance(notes)
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
) -> PerformanceFeedback:
    """Compute strict lesson-feedback metrics from expected-vs-played comparison rows."""
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
