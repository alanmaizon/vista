"""Minimal symbolic music models for Eurydice."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
INTERVAL_NAMES = {
    0: "unison",
    1: "minor second",
    2: "major second",
    3: "minor third",
    4: "major third",
    5: "perfect fourth",
    6: "tritone",
    7: "perfect fifth",
    8: "minor sixth",
    9: "major sixth",
    10: "minor seventh",
    11: "major seventh",
    12: "octave",
}


def midi_to_note_name(midi_note: int) -> str:
    """Convert a MIDI note number to a note label like A4."""
    pitch_class = midi_note % 12
    octave = (midi_note // 12) - 1
    return f"{NOTE_NAMES[pitch_class]}{octave}"


def frequency_to_midi(frequency_hz: float) -> int:
    """Convert frequency to the nearest MIDI note number."""
    return round(69 + 12 * log2(frequency_hz / 440.0))


@dataclass(frozen=True)
class NoteEvent:
    """A single detected note event in a phrase."""

    midi_note: int
    note_name: str
    frequency_hz: float
    start_ms: int
    duration_ms: int
    confidence: float

    @property
    def pitch_class(self) -> int:
        return self.midi_note % 12


@dataclass(frozen=True)
class SymbolicPhrase:
    """A simple symbolic transcription result for a short phrase."""

    kind: str
    notes: tuple[NoteEvent, ...]
    duration_ms: int
    confidence: float
    interval_hint: str | None = None
    harmony_hint: str | None = None
    summary: str = ""
    warnings: tuple[str, ...] = ()


def interval_name_for_semitones(semitones: int) -> str:
    """Return a human-readable interval name for a semitone distance."""
    semitones = abs(semitones)
    octaves, remainder = divmod(semitones, 12)
    base = INTERVAL_NAMES.get(remainder, f"{remainder} semitones")
    if octaves == 0:
        return base
    if remainder == 0:
        return "octave" if octaves == 1 else f"{octaves} octaves"
    return f"{base} plus {octaves} octave{'s' if octaves != 1 else ''}"
