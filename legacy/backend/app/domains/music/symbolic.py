"""Minimal symbolic music models for Eurydice."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2
import re


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
PITCH_CLASS_BY_NAME = {
    "C": 0,
    "B#": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "FB": 4,
    "E#": 5,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
    "CB": 11,
}
DURATION_BEATS = {
    "w": 4.0,
    "h": 2.0,
    "q": 1.0,
    "e": 0.5,
    "8": 0.5,
    "s": 0.25,
    "16": 0.25,
}
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


def note_name_to_midi(note_name: str) -> int:
    """Convert a note name like C#4 or Bb3 to a MIDI note number."""
    match = re.fullmatch(r"([A-Ga-g])([#bB]?)(-?\d+)", note_name.strip())
    if not match:
        raise ValueError(f"Invalid note name: {note_name}")
    letter, accidental, octave_raw = match.groups()
    pitch_name = f"{letter.upper()}{accidental.upper()}".rstrip()
    if pitch_name not in PITCH_CLASS_BY_NAME:
        raise ValueError(f"Unsupported note spelling: {note_name}")
    octave = int(octave_raw)
    return (octave + 1) * 12 + PITCH_CLASS_BY_NAME[pitch_name]


@dataclass(frozen=True)
class NoteEvent:
    """A single detected note event in a phrase."""

    midi_note: int
    note_name: str
    frequency_hz: float
    start_ms: int
    duration_ms: int
    confidence: float
    beats: float | None = None

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
    tempo_bpm: float | None = None
    performance_feedback: dict[str, float] | None = None


@dataclass(frozen=True)
class ScoreNote:
    """A note token in a simple imported score."""

    note_name: str
    midi_note: int
    duration_code: str
    beats: float
    token: str


@dataclass(frozen=True)
class ScoreMeasure:
    """A simple sequence of score notes inside one bar."""

    index: int
    notes: tuple[ScoreNote, ...]
    total_beats: float


@dataclass(frozen=True)
class SymbolicScore:
    """A minimal imported score structure for Eurydice."""

    format: str
    measures: tuple[ScoreMeasure, ...]
    note_count: int
    normalized: str
    summary: str
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


def parse_score_token(token: str) -> ScoreNote:
    """Parse a simple score token like C4/q or Bb3/h."""
    if "/" not in token:
        raise ValueError(f"Score token must include a duration, for example C4/q: {token}")
    raw_note, raw_duration = token.split("/", 1)
    duration_code = raw_duration.strip().lower()
    is_dotted = duration_code.endswith(".")
    if is_dotted:
        duration_code = duration_code[:-1]
    if duration_code not in DURATION_BEATS:
        raise ValueError(f"Unsupported duration code in token: {token}")
    beats = DURATION_BEATS[duration_code] * (1.5 if is_dotted else 1.0)
    midi_note = note_name_to_midi(raw_note)
    normalized_note = midi_to_note_name(midi_note)
    token_duration = f"{duration_code}{'.' if is_dotted else ''}"
    return ScoreNote(
        note_name=normalized_note,
        midi_note=midi_note,
        duration_code=token_duration,
        beats=beats,
        token=f"{normalized_note}/{token_duration}",
    )


def import_simple_score(source_text: str, *, time_signature: str = "4/4") -> SymbolicScore:
    """Import a simple note-line score such as 'C4/q D4/q | E4/h G4/h'."""
    cleaned = source_text.strip()
    if not cleaned:
        raise ValueError("source_text is required.")

    warnings: list[str] = []
    measures: list[ScoreMeasure] = []
    normalized_measures: list[str] = []
    note_count = 0

    try:
        beats_per_measure = float(time_signature.split("/", 1)[0])
    except (ValueError, IndexError):
        beats_per_measure = 4.0
        warnings.append("Time signature was invalid. Assumed 4/4.")

    raw_measures = [chunk.strip() for chunk in cleaned.split("|")]
    for index, raw_measure in enumerate(raw_measures, start=1):
        if not raw_measure:
            continue
        note_tokens = [token for token in raw_measure.split() if token]
        if not note_tokens:
            continue
        notes = tuple(parse_score_token(token) for token in note_tokens)
        total_beats = round(sum(note.beats for note in notes), 3)
        note_count += len(notes)
        if abs(total_beats - beats_per_measure) > 0.001:
            warnings.append(
                f"Measure {index} totals {total_beats:g} beats, which does not match {time_signature}."
            )
        measures.append(ScoreMeasure(index=index, notes=notes, total_beats=total_beats))
        normalized_measures.append(" ".join(note.token for note in notes))

    if not measures:
        raise ValueError("No score tokens were found.")

    summary = (
        f"Imported {note_count} note{'s' if note_count != 1 else ''} "
        f"across {len(measures)} measure{'s' if len(measures) != 1 else ''}."
    )
    if warnings:
        summary += " Review the beat warnings before treating this as exact notation."

    return SymbolicScore(
        format="NOTE_LINE",
        measures=tuple(measures),
        note_count=note_count,
        normalized=" | ".join(normalized_measures),
        summary=summary,
        warnings=tuple(warnings),
    )


def score_to_dict(score: SymbolicScore) -> dict[str, object]:
    """Convert a symbolic score into a JSON-serializable payload."""
    return {
        "format": score.format,
        "note_count": score.note_count,
        "normalized": score.normalized,
        "summary": score.summary,
        "warnings": list(score.warnings),
        "measures": [
            {
                "index": measure.index,
                "total_beats": measure.total_beats,
                "notes": [
                    {
                        "note_name": note.note_name,
                        "midi_note": note.midi_note,
                        "duration_code": note.duration_code,
                        "beats": note.beats,
                        "token": note.token,
                    }
                    for note in measure.notes
                ],
            }
            for measure in score.measures
        ],
    }
