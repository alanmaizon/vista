"""Monophonic-first audio transcription utilities for Eurydice."""

from __future__ import annotations

import base64
import binascii
import math
import re
import statistics
import struct
from dataclasses import asdict

from .crepe import estimate_pitch_crepe
from .feedback import feedback_from_phrase
from .pitch import estimate_pitch_fastyin
from .symbolic import (
    NOTE_NAMES,
    NoteEvent,
    SymbolicPhrase,
    frequency_to_midi,
    interval_name_for_semitones,
    midi_to_note_name,
)


PCM_MIME_RE = re.compile(r"^audio/pcm(?:;rate=(?P<rate>\d+))?$", re.IGNORECASE)
MIN_CONFIDENCE = 0.36
SILENCE_THRESHOLD = 0.02
MAX_NOTES = 12


class MusicTranscriptionError(ValueError):
    """Raised when a transcription request cannot be processed."""


def parse_pcm_mime(mime: str) -> int:
    """Parse a PCM mime string and return the sample rate."""
    match = PCM_MIME_RE.match((mime or "").strip())
    if not match:
        raise MusicTranscriptionError("Only raw mono PCM audio is supported for transcription right now.")
    sample_rate = int(match.group("rate") or "16000")
    if sample_rate < 8000 or sample_rate > 48000:
        raise MusicTranscriptionError("PCM sample rate must be between 8000 and 48000 Hz.")
    return sample_rate


def decode_audio_b64(audio_b64: str) -> bytes:
    """Decode a base64-encoded audio payload."""
    if not audio_b64:
        raise MusicTranscriptionError("audio_b64 is required.")
    try:
        return base64.b64decode(audio_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MusicTranscriptionError("audio_b64 must be valid base64.") from exc


def _pcm16le_to_floats(audio_bytes: bytes) -> list[float]:
    if len(audio_bytes) < 2:
        return []
    sample_count = len(audio_bytes) // 2
    usable = audio_bytes[: sample_count * 2]
    samples = [
        sample / 32768.0
        for (sample,) in struct.iter_unpack("<h", usable)
    ]
    return samples


def _frame_rms(samples: list[float], start: int, stop: int) -> float:
    if stop <= start:
        return 0.0
    energy = 0.0
    for sample in samples[start:stop]:
        energy += sample * sample
    return math.sqrt(energy / (stop - start))


def _find_active_segments(samples: list[float], sample_rate: int) -> list[tuple[int, int]]:
    if not samples:
        return []

    frame_size = max(160, sample_rate // 50)  # ~20 ms
    frame_count = max(1, len(samples) // frame_size)
    frame_levels: list[float] = []
    max_rms = 0.0

    for frame_index in range(frame_count):
        start = frame_index * frame_size
        stop = min(len(samples), start + frame_size)
        level = _frame_rms(samples, start, stop)
        frame_levels.append(level)
        if level > max_rms:
            max_rms = level

    threshold = max(SILENCE_THRESHOLD, max_rms * 0.24)
    min_frames = 2
    merge_gap_frames = 3
    segments: list[tuple[int, int]] = []
    active_start_frame: int | None = None
    last_active_frame: int | None = None

    for frame_index, level in enumerate(frame_levels):
        if level >= threshold:
            if active_start_frame is None:
                active_start_frame = frame_index
            last_active_frame = frame_index
            continue

        if active_start_frame is None or last_active_frame is None:
            continue

        gap = frame_index - last_active_frame
        if gap <= merge_gap_frames:
            continue

        if (last_active_frame - active_start_frame + 1) >= min_frames:
            segments.append(
                (
                    active_start_frame * frame_size,
                    min(len(samples), (last_active_frame + 1) * frame_size),
                )
            )
        active_start_frame = None
        last_active_frame = None

    if active_start_frame is not None and last_active_frame is not None:
        if (last_active_frame - active_start_frame + 1) >= min_frames:
            segments.append(
                (
                    active_start_frame * frame_size,
                    min(len(samples), (last_active_frame + 1) * frame_size),
                )
            )

    return segments


def _estimate_pitch(segment: list[float], sample_rate: int) -> tuple[float | None, float]:
    fastyin_estimate = estimate_pitch_fastyin(segment, sample_rate=sample_rate)
    crepe_estimate = estimate_pitch_crepe(segment, sample_rate=sample_rate)

    if fastyin_estimate is None and crepe_estimate is None:
        return None, 0.0
    if fastyin_estimate is None:
        return crepe_estimate.frequency_hz, crepe_estimate.confidence
    if crepe_estimate is None:
        return fastyin_estimate.frequency_hz, fastyin_estimate.confidence

    semitone_delta = abs(12.0 * math.log2(crepe_estimate.frequency_hz / fastyin_estimate.frequency_hz))
    if semitone_delta <= 0.35:
        blended_frequency = (fastyin_estimate.frequency_hz + crepe_estimate.frequency_hz) / 2.0
        blended_confidence = max(fastyin_estimate.confidence, crepe_estimate.confidence)
        return blended_frequency, min(1.0, blended_confidence)

    if crepe_estimate.confidence >= fastyin_estimate.confidence + 0.15:
        return crepe_estimate.frequency_hz, crepe_estimate.confidence

    return fastyin_estimate.frequency_hz, max(0.0, min(fastyin_estimate.confidence, 0.82))


_FRAME_CONFIDENCE_MIN = 0.3
_PITCH_CHANGE_CENTS = 80
_MIN_NOTE_DURATION_MS = 80


def _build_pitch_contour(
    samples: list[float],
    sample_rate: int,
    hop_ms: int = 10,
) -> list[tuple[float | None, float]]:
    """Estimate f0 at every *hop_ms* across the clip.

    Returns a list of (frequency_hz | None, confidence) per frame.
    """
    hop_samples = max(1, int(sample_rate * hop_ms / 1000))
    # Use a window ~2x the hop for overlap
    window_samples = hop_samples * 4
    contour: list[tuple[float | None, float]] = []

    for start in range(0, len(samples), hop_samples):
        end = min(len(samples), start + window_samples)
        # Minimum window for reliable pitch estimation (~20 ms)
        if end - start < sample_rate // 50:
            contour.append((None, 0.0))
            continue
        frame = samples[start:end]
        freq, conf = _estimate_pitch(frame, sample_rate)
        contour.append((freq, conf))

    return contour


def _segment_notes_from_contour(
    contour: list[tuple[float | None, float]],
    sample_rate: int,
    hop_ms: int = 10,
    confidence_min: float = _FRAME_CONFIDENCE_MIN,
    pitch_change_cents: float = _PITCH_CHANGE_CENTS,
    min_note_duration_ms: float = _MIN_NOTE_DURATION_MS,
) -> list[NoteEvent]:
    """Group contiguous contour frames into note events.

    Frames are grouped when confidence is above *confidence_min* and pitch
    stays within *pitch_change_cents* of the running median.  Each resulting
    note must last at least *min_note_duration_ms*.
    """
    events: list[NoteEvent] = []
    min_frames = max(1, int(min_note_duration_ms / hop_ms))

    # Accumulate frames for current note region
    region_freqs: list[float] = []
    region_confs: list[float] = []
    region_start: int | None = None

    def _flush() -> None:
        if region_start is None or len(region_freqs) < min_frames:
            return
        sorted_freqs = sorted(region_freqs)
        median_freq = sorted_freqs[len(sorted_freqs) // 2]
        midi_note = frequency_to_midi(median_freq)
        avg_conf = sum(region_confs) / len(region_confs)
        start_ms = region_start * hop_ms
        duration_ms = max(1, len(region_freqs) * hop_ms)
        events.append(
            NoteEvent(
                midi_note=midi_note,
                note_name=midi_to_note_name(midi_note),
                frequency_hz=round(median_freq, 2),
                start_ms=start_ms,
                duration_ms=duration_ms,
                confidence=round(avg_conf, 3),
            )
        )

    for frame_idx, (freq, conf) in enumerate(contour):
        if freq is None or conf < confidence_min:
            _flush()
            region_freqs = []
            region_confs = []
            region_start = None
            continue

        if region_start is None:
            # Start a new region
            region_start = frame_idx
            region_freqs = [freq]
            region_confs = [conf]
        else:
            # Check pitch deviation from running median
            sorted_freqs = sorted(region_freqs)
            median_freq = sorted_freqs[len(sorted_freqs) // 2]
            if median_freq > 0 and freq > 0:
                cents = abs(1200.0 * math.log2(freq / median_freq))
            else:
                cents = float("inf")

            if cents <= pitch_change_cents:
                region_freqs.append(freq)
                region_confs.append(conf)
            else:
                # Pitch jumped — flush current note and start new
                _flush()
                region_start = frame_idx
                region_freqs = [freq]
                region_confs = [conf]

    _flush()
    return events


def _dedupe_similar_notes(events: list[NoteEvent]) -> list[NoteEvent]:
    deduped: list[NoteEvent] = []
    for event in events:
        if deduped:
            previous = deduped[-1]
            if previous.midi_note == event.midi_note and abs(previous.start_ms - event.start_ms) <= 80:
                merged_duration = max(previous.duration_ms, event.duration_ms)
                merged_confidence = max(previous.confidence, event.confidence)
                deduped[-1] = NoteEvent(
                    midi_note=previous.midi_note,
                    note_name=previous.note_name,
                    frequency_hz=previous.frequency_hz,
                    start_ms=previous.start_ms,
                    duration_ms=merged_duration,
                    confidence=merged_confidence,
                )
                continue
        deduped.append(event)
    return deduped


def _harmony_hint(events: list[NoteEvent]) -> str | None:
    pitch_classes: list[int] = []
    for event in events:
        if event.pitch_class not in pitch_classes:
            pitch_classes.append(event.pitch_class)
    if len(pitch_classes) < 3:
        return None

    for root in pitch_classes:
        normalized = sorted((pitch - root) % 12 for pitch in pitch_classes)
        if {0, 4, 7}.issubset(normalized):
            return f"Likely {NOTE_NAMES[root]} major harmony."
        if {0, 3, 7}.issubset(normalized):
            return f"Likely {NOTE_NAMES[root]} minor harmony."
    return None


def _interval_hint(events: list[NoteEvent]) -> str | None:
    if len(events) < 2:
        return None
    semitones = events[1].midi_note - events[0].midi_note
    direction = "ascending" if semitones >= 0 else "descending"
    return f"{direction.capitalize()} {interval_name_for_semitones(semitones)}."


def _estimate_tempo(events: list[NoteEvent]) -> float | None:
    """Estimate tempo in BPM from inter-onset intervals of note events.

    Returns the estimated BPM if at least two notes exist, else ``None``.
    """
    if len(events) < 2:
        return None
    ioi_ms_values: list[float] = []
    for i in range(1, len(events)):
        ioi = events[i].start_ms - events[i - 1].start_ms
        if ioi > 0:
            ioi_ms_values.append(float(ioi))
    if not ioi_ms_values:
        return None
    median_ioi_ms = statistics.median(ioi_ms_values)
    if median_ioi_ms <= 0:
        return None
    return round(60000.0 / median_ioi_ms, 1)


def _add_beats_to_events(events: list[NoteEvent], tempo_bpm: float | None) -> list[NoteEvent]:
    """Return a copy of *events* with the ``beats`` field populated."""
    if not tempo_bpm or tempo_bpm <= 0:
        return events
    beat_ms = 60000.0 / tempo_bpm
    return [
        NoteEvent(
            midi_note=e.midi_note,
            note_name=e.note_name,
            frequency_hz=e.frequency_hz,
            start_ms=e.start_ms,
            duration_ms=e.duration_ms,
            confidence=e.confidence,
            beats=round(e.duration_ms / beat_ms, 3),
        )
        for e in events
    ]


def transcribe_pcm16(
    audio_bytes: bytes,
    *,
    sample_rate: int = 16000,
    expected: str = "AUTO",
    max_notes: int = 8,
) -> SymbolicPhrase:
    """Transcribe a short monophonic PCM clip into a symbolic phrase."""
    if max_notes < 1 or max_notes > MAX_NOTES:
        raise MusicTranscriptionError(f"max_notes must be between 1 and {MAX_NOTES}.")

    samples = _pcm16le_to_floats(audio_bytes)
    if not samples:
        raise MusicTranscriptionError("The audio clip is empty.")

    # Frame-level pitch contour for improved segmentation
    contour = _build_pitch_contour(samples, sample_rate)
    events = _segment_notes_from_contour(contour, sample_rate)
    warnings: list[str] = []

    if not events:
        # Fall back to legacy energy-gate segmentation
        segments = _find_active_segments(samples, sample_rate)
        if not segments:
            warnings.append("No stable pitched phrase was detected. Try a cleaner, slower monophonic replay.")
        for start, stop in segments[:max_notes]:
            segment = samples[start:stop]
            frequency_hz, confidence = _estimate_pitch(segment, sample_rate)
            if frequency_hz is None or confidence < MIN_CONFIDENCE:
                continue
            midi_note = frequency_to_midi(frequency_hz)
            events.append(
                NoteEvent(
                    midi_note=midi_note,
                    note_name=midi_to_note_name(midi_note),
                    frequency_hz=round(frequency_hz, 2),
                    start_ms=round(start * 1000 / sample_rate),
                    duration_ms=max(1, round((stop - start) * 1000 / sample_rate)),
                    confidence=round(confidence, 3),
                )
            )

    events = _dedupe_similar_notes(events)
    events = events[:max_notes]

    # Estimate tempo and attach beats to each note
    tempo_bpm = _estimate_tempo(events)
    events = _add_beats_to_events(events, tempo_bpm)

    if any(event.confidence < 0.6 for event in events):
        warnings.append("One or more detected notes are lower confidence. Replay slowly for a cleaner result.")

    expected_upper = (expected or "AUTO").strip().upper()
    if expected_upper == "CHORD":
        warnings.append(
            "Exact polyphonic chord voicing is not guaranteed in this monophonic-first MVP. "
            "Play notes one by one or use a reference score for tighter verification."
        )

    if not events:
        feedback = feedback_from_phrase(samples=samples, notes=(), confidence=0.0)
        return SymbolicPhrase(
            kind="unknown",
            notes=(),
            duration_ms=round(len(samples) * 1000 / sample_rate),
            confidence=0.0,
            summary="I could not confirm a stable pitched phrase from this clip.",
            warnings=tuple(dict.fromkeys(warnings)),
            performance_feedback=feedback.to_dict(),
        )

    if len(events) == 1:
        kind = "single_note"
    elif len(events) == 2:
        kind = "interval"
    else:
        kind = "melody_fragment"

    if expected_upper == "ARPEGGIO" and len(events) >= 3:
        kind = "arpeggio_candidate"

    avg_confidence = round(sum(event.confidence for event in events) / len(events), 3)
    feedback = feedback_from_phrase(samples=samples, notes=events, confidence=avg_confidence)
    interval_hint = _interval_hint(events)
    harmony_hint = _harmony_hint(events)

    summary_parts = [f"Detected {len(events)} note{'s' if len(events) != 1 else ''}"]
    summary_parts.append(": " + ", ".join(event.note_name for event in events))
    if harmony_hint:
        summary_parts.append(f". {harmony_hint}")
    elif interval_hint:
        summary_parts.append(f". {interval_hint}")
    summary_parts.append(f" Confidence {round(avg_confidence * 100)}%.")

    return SymbolicPhrase(
        kind=kind,
        notes=tuple(events),
        duration_ms=round(len(samples) * 1000 / sample_rate),
        confidence=avg_confidence,
        interval_hint=interval_hint,
        harmony_hint=harmony_hint,
        summary="".join(summary_parts).strip(),
        warnings=tuple(dict.fromkeys(warnings)),
        tempo_bpm=tempo_bpm,
        performance_feedback=feedback.to_dict(),
    )


def transcription_to_dict(result: SymbolicPhrase) -> dict:
    """Convert a symbolic phrase to a JSON-serializable dict."""
    return {
        "kind": result.kind,
        "duration_ms": result.duration_ms,
        "confidence": result.confidence,
        "interval_hint": result.interval_hint,
        "harmony_hint": result.harmony_hint,
        "summary": result.summary,
        "warnings": list(result.warnings),
        "tempo_bpm": result.tempo_bpm,
        "performance_feedback": result.performance_feedback,
        "notes": [asdict(note) for note in result.notes],
    }
