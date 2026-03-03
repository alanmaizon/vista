"""Monophonic-first audio transcription utilities for Eurydice."""

from __future__ import annotations

import base64
import binascii
import math
import re
import struct
from dataclasses import asdict

from .music_crepe import estimate_pitch_crepe
from .music_pitch import estimate_pitch_fastyin
from .music_symbolic import (
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

    segments = _find_active_segments(samples, sample_rate)
    events: list[NoteEvent] = []
    warnings: list[str] = []

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
    if any(event.confidence < 0.6 for event in events):
        warnings.append("One or more detected notes are lower confidence. Replay slowly for a cleaner result.")

    expected_upper = (expected or "AUTO").strip().upper()
    if expected_upper == "CHORD":
        warnings.append(
            "Exact polyphonic chord voicing is not guaranteed in this monophonic-first MVP. "
            "Play notes one by one or use a reference score for tighter verification."
        )

    if not events:
        return SymbolicPhrase(
            kind="unknown",
            notes=(),
            duration_ms=round(len(samples) * 1000 / sample_rate),
            confidence=0.0,
            summary="I could not confirm a stable pitched phrase from this clip.",
            warnings=tuple(dict.fromkeys(warnings)),
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
        "notes": [asdict(note) for note in result.notes],
    }
