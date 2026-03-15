"""Optional CREPE-assisted pitch confirmation for Eurydice."""

from __future__ import annotations

import math

from .pitch import PitchEstimate


def crepe_runtime_status() -> tuple[bool, str]:
    """Report whether the optional CREPE stack is importable."""
    try:
        import numpy  # noqa: F401
        import crepe  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        return False, f"{exc.__class__.__name__}: {exc}"
    return True, "crepe module detected"


def estimate_pitch_crepe(
    samples: list[float],
    *,
    sample_rate: int,
    step_size_ms: int = 10,
) -> PitchEstimate | None:
    """Estimate pitch with CREPE when the optional dependency is installed."""
    if len(samples) < sample_rate // 20:
        return None

    try:
        import numpy as np
        import crepe
    except Exception:  # pragma: no cover - depends on optional runtime
        return None

    audio = np.asarray(samples, dtype=np.float32)
    if audio.size == 0:
        return None

    try:
        _, frequencies, confidences, _ = crepe.predict(
            audio,
            sample_rate,
            viterbi=True,
            step_size=step_size_ms,
            verbose=0,
        )
    except TypeError:  # pragma: no cover - older crepe signatures
        try:
            _, frequencies, confidences, _ = crepe.predict(
                audio,
                sample_rate,
                viterbi=True,
                step_size=step_size_ms,
            )
        except Exception:
            return None
    except Exception:  # pragma: no cover - runtime/model errors
        return None

    weighted_frequency = 0.0
    total_weight = 0.0
    best_confidence = 0.0
    for frequency_hz, confidence in zip(frequencies, confidences):
        try:
            frequency_hz = float(frequency_hz)
            confidence = float(confidence)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(frequency_hz) or frequency_hz <= 0.0:
            continue
        if not math.isfinite(confidence) or confidence <= 0.0:
            continue
        weighted_frequency += frequency_hz * confidence
        total_weight += confidence
        best_confidence = max(best_confidence, confidence)

    if total_weight <= 0.0 or best_confidence <= 0.0:
        return None

    return PitchEstimate(
        frequency_hz=weighted_frequency / total_weight,
        confidence=max(0.0, min(1.0, best_confidence)),
    )
