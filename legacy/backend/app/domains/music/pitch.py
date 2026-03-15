"""Pitch detection helpers for Eurydice."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PitchEstimate:
    """A pitch estimate returned by the FastYIN-style detector."""

    frequency_hz: float
    confidence: float


def _difference_function(samples: list[float], max_lag: int) -> list[float]:
    values = [0.0] * (max_lag + 1)
    sample_length = len(samples)
    for lag in range(1, max_lag + 1):
        diff = 0.0
        upper = sample_length - lag
        for index in range(upper):
            delta = samples[index] - samples[index + lag]
            diff += delta * delta
        values[lag] = diff
    return values


def _cumulative_mean_normalized_difference(diff_values: list[float]) -> list[float]:
    normalized = [1.0] * len(diff_values)
    running_total = 0.0
    for lag in range(1, len(diff_values)):
        running_total += diff_values[lag]
        if running_total <= 0.0:
            normalized[lag] = 1.0
            continue
        normalized[lag] = diff_values[lag] * lag / running_total
    return normalized


def _refine_lag(candidate_lag: int, normalized: list[float]) -> float:
    if candidate_lag <= 1 or candidate_lag >= len(normalized) - 1:
        return float(candidate_lag)
    left = normalized[candidate_lag - 1]
    center = normalized[candidate_lag]
    right = normalized[candidate_lag + 1]
    denominator = left - (2.0 * center) + right
    if abs(denominator) < 1e-9:
        return float(candidate_lag)
    offset = 0.5 * (left - right) / denominator
    return candidate_lag + max(-0.5, min(0.5, offset))


def estimate_pitch_fastyin(
    samples: list[float],
    *,
    sample_rate: int,
    min_freq: float = 82.41,
    max_freq: float = 1046.5,
    threshold: float = 0.12,
) -> PitchEstimate | None:
    """Estimate monophonic pitch using a FastYIN-style CMNDF search."""
    if len(samples) < sample_rate // 20:
        return None

    mean = sum(samples) / len(samples)
    centered = [sample - mean for sample in samples]
    energy = sum(sample * sample for sample in centered)
    if energy <= 0.0:
        return None

    min_lag = max(2, int(sample_rate / max_freq))
    max_lag = min(len(centered) - 1, int(sample_rate / min_freq))
    if max_lag <= min_lag:
        return None

    diff_values = _difference_function(centered, max_lag)
    normalized = _cumulative_mean_normalized_difference(diff_values)

    candidate_lag: int | None = None
    best_lag = min_lag
    best_value = normalized[min_lag]

    for lag in range(min_lag, max_lag + 1):
        value = normalized[lag]
        if value < best_value:
            best_value = value
            best_lag = lag

        if value <= threshold:
            while lag + 1 <= max_lag and normalized[lag + 1] < value:
                lag += 1
                value = normalized[lag]
            candidate_lag = lag
            break

    if candidate_lag is None:
        candidate_lag = best_lag

    refined_lag = _refine_lag(candidate_lag, normalized)
    if refined_lag <= 0.0:
        return None

    confidence = max(0.0, min(1.0, 1.0 - normalized[candidate_lag]))
    if confidence <= 0.0:
        return None

    frequency_hz = sample_rate / refined_lag
    if not math.isfinite(frequency_hz) or frequency_hz <= 0.0:
        return None

    return PitchEstimate(
        frequency_hz=frequency_hz,
        confidence=confidence,
    )
