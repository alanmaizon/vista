"""Score rendering helpers for Eurydice."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from .models import MusicScore


DURATION_METADATA = {
    "w": {"divisions": 16, "type": "whole"},
    "h": {"divisions": 8, "type": "half"},
    "q": {"divisions": 4, "type": "quarter"},
    "e": {"divisions": 2, "type": "eighth"},
    "8": {"divisions": 2, "type": "eighth"},
    "s": {"divisions": 1, "type": "16th"},
    "16": {"divisions": 1, "type": "16th"},
}


@dataclass(frozen=True)
class RenderedMusicScore:
    """Rendered notation payload with Verovio fallback metadata."""

    render_backend: str
    verovio_available: bool
    musicxml: str
    svg: str | None
    warnings: tuple[str, ...] = ()


def verovio_runtime_status() -> tuple[bool, str]:
    """Return whether the Verovio Python module is importable."""
    available = importlib.util.find_spec("verovio") is not None
    if available:
        return True, "verovio module detected"
    return False, "verovio module is not installed"


def _split_note_name(note_name: str) -> tuple[str, int | None, int]:
    head = note_name.rstrip("0123456789-")
    octave = int(note_name[len(head) :])
    step = head[0].upper()
    accidental = head[1:] if len(head) > 1 else ""
    alter = {"#": 1, "B": -1, "b": -1}.get(accidental, None)
    return step, alter, octave


def _duration_metadata(duration_code: str) -> tuple[int, str, bool]:
    dotted = duration_code.endswith(".")
    base_code = duration_code[:-1] if dotted else duration_code
    meta = DURATION_METADATA.get(base_code)
    if meta is None:
        raise ValueError(f"Unsupported duration code: {duration_code}")
    divisions = meta["divisions"] + (meta["divisions"] // 2 if dotted else 0)
    return divisions, meta["type"], dotted


def _default_clef(score: MusicScore) -> tuple[str, int]:
    midi_notes: list[int] = []
    for measure in score.measures or []:
        for note in measure.get("notes", []):
            midi_note = note.get("midi_note")
            if isinstance(midi_note, int):
                midi_notes.append(midi_note)
    if not midi_notes:
        return "G", 2
    average = sum(midi_notes) / len(midi_notes)
    return ("F", 4) if average < 60 else ("G", 2)


def score_to_musicxml(score: MusicScore) -> str:
    """Convert a stored symbolic score into a minimal MusicXML document."""
    beats_raw, beat_type_raw = (score.time_signature or "4/4").split("/", 1)
    beats = escape(beats_raw or "4")
    beat_type = escape(beat_type_raw or "4")
    clef_sign, clef_line = _default_clef(score)

    measure_xml: list[str] = []
    for measure in score.measures or []:
        measure_number = int(measure.get("index", len(measure_xml) + 1))
        note_xml: list[str] = []
        for note in measure.get("notes", []):
            note_name = str(note.get("note_name", "C4"))
            duration_code = str(note.get("duration_code", "q"))
            step, alter, octave = _split_note_name(note_name)
            duration_divisions, note_type, dotted = _duration_metadata(duration_code)
            pitch_parts = [
                f"<step>{escape(step)}</step>",
            ]
            if alter is not None:
                pitch_parts.append(f"<alter>{alter}</alter>")
            pitch_parts.append(f"<octave>{octave}</octave>")
            dot_xml = "<dot/>" if dotted else ""
            note_xml.append(
                "".join(
                    [
                        "<note>",
                        "<pitch>",
                        *pitch_parts,
                        "</pitch>",
                        f"<duration>{duration_divisions}</duration>",
                        f"<type>{escape(note_type)}</type>",
                        dot_xml,
                        "</note>",
                    ]
                )
            )

        if measure_number == 1:
            attributes = (
                "<attributes>"
                "<divisions>4</divisions>"
                "<key><fifths>0</fifths></key>"
                f"<time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time>"
                f"<clef><sign>{clef_sign}</sign><line>{clef_line}</line></clef>"
                "</attributes>"
            )
        else:
            attributes = ""
        measure_xml.append(
            f'<measure number="{measure_number}">{attributes}{"".join(note_xml)}</measure>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">'
        '<score-partwise version="4.0">'
        "<part-list><score-part id=\"P1\"><part-name>Eurydice</part-name></score-part></part-list>"
        f"<part id=\"P1\">{''.join(measure_xml)}</part>"
        "</score-partwise>"
    )


def _build_verovio_toolkit() -> Any:
    import verovio  # type: ignore

    toolkit_factory = getattr(verovio, "toolkit", None)
    if callable(toolkit_factory):
        return toolkit_factory()
    toolkit_class = getattr(verovio, "Toolkit", None) or getattr(verovio, "VerovioToolkit", None)
    if toolkit_class is not None:
        return toolkit_class()
    raise RuntimeError("Unsupported Verovio toolkit API")


def _render_with_verovio(musicxml: str) -> str:
    toolkit = _build_verovio_toolkit()
    set_options = getattr(toolkit, "setOptions", None) or getattr(toolkit, "set_options", None)
    if callable(set_options):
        set_options({"pageWidth": 1600, "scale": 42})

    load_data = getattr(toolkit, "loadData", None) or getattr(toolkit, "load_data", None)
    if not callable(load_data):
        raise RuntimeError("Verovio toolkit does not expose loadData")
    load_data(musicxml)

    render_svg = getattr(toolkit, "renderToSVG", None) or getattr(toolkit, "render_to_svg", None)
    if not callable(render_svg):
        raise RuntimeError("Verovio toolkit does not expose renderToSVG")

    for args in ((), (1,), (1, False)):
        try:
            rendered = render_svg(*args)
        except TypeError:
            continue
        if isinstance(rendered, str) and rendered.strip():
            return rendered
    raise RuntimeError("Verovio did not return an SVG document")


def render_music_score(score: MusicScore) -> RenderedMusicScore:
    """Render a stored symbolic score with Verovio when available."""
    musicxml = score_to_musicxml(score)
    available, detail = verovio_runtime_status()
    if not available:
        return RenderedMusicScore(
            render_backend="MUSICXML_FALLBACK",
            verovio_available=False,
            musicxml=musicxml,
            svg=None,
            warnings=(detail,),
        )

    try:
        svg = _render_with_verovio(musicxml)
    except Exception as exc:
        return RenderedMusicScore(
            render_backend="MUSICXML_FALLBACK",
            verovio_available=True,
            musicxml=musicxml,
            svg=None,
            warnings=(f"Verovio render failed: {exc}",),
        )

    return RenderedMusicScore(
        render_backend="VEROVIO",
        verovio_available=True,
        musicxml=musicxml,
        svg=svg,
        warnings=(),
    )
