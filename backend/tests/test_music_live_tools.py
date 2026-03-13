from __future__ import annotations

import uuid

import pytest

from app.domains.music import live_tools
from app.domains.music.symbolic import SymbolicPhrase


@pytest.mark.asyncio
async def test_lesson_action_tool_rejects_unknown_args() -> None:
    with pytest.raises(live_tools.LiveMusicToolError) as exc:
        await live_tools.run_live_music_tool(
            None,  # type: ignore[arg-type]
            user_id="user-1",
            tool_name="lesson_action",
            args={
                "source_text": "C4/q D4/q",
                "time_signature": "4/4",
                "unexpected_field": "not-allowed",
            },
        )
    assert "Extra inputs are not permitted" in str(exc.value)


@pytest.mark.asyncio
async def test_lesson_step_tool_validates_score_id() -> None:
    with pytest.raises(live_tools.LiveMusicToolError) as exc:
        await live_tools.run_live_music_tool(
            None,  # type: ignore[arg-type]
            user_id="user-1",
            tool_name="lesson_step",
            args={"score_id": "not-a-uuid", "lesson_stage": "idle"},
        )
    assert "valid UUID" in str(exc.value)


@pytest.mark.asyncio
async def test_render_score_tool_returns_model_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    score_id = uuid.uuid4()

    class DummyResponse:
        def model_dump(self, mode: str = "json") -> dict[str, str]:
            del mode
            return {"score_id": str(score_id), "render_backend": "VEROVIO"}

    async def fake_render_stored_music_score(*_args, **_kwargs) -> DummyResponse:
        return DummyResponse()

    monkeypatch.setattr(live_tools, "render_stored_music_score", fake_render_stored_music_score)
    payload = await live_tools.run_live_music_tool(
        None,  # type: ignore[arg-type]
        user_id="user-1",
        tool_name="render_score",
        args={"score_id": str(score_id)},
    )
    assert payload == {"score_id": str(score_id), "render_backend": "VEROVIO"}


@pytest.mark.asyncio
async def test_transcribe_tool_returns_phrase_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    phrase = SymbolicPhrase(
        kind="single_note",
        notes=(),
        duration_ms=400,
        confidence=0.91,
        summary="Detected A4.",
    )

    monkeypatch.setattr(live_tools, "parse_pcm_mime", lambda _mime: 16000)
    monkeypatch.setattr(live_tools, "decode_audio_b64", lambda _audio_b64: b"\x00\x00")
    monkeypatch.setattr(live_tools, "transcribe_pcm16", lambda *_args, **_kwargs: phrase)
    monkeypatch.setattr(
        live_tools,
        "transcription_to_dict",
        lambda result: {"kind": result.kind, "summary": result.summary, "confidence": result.confidence},
    )

    payload = await live_tools.run_live_music_tool(
        None,  # type: ignore[arg-type]
        user_id="user-1",
        tool_name="transcribe",
        args={
            "audio_b64": "AA==",
            "mime": "audio/pcm;rate=16000",
            "expected": "AUTO",
            "max_notes": 8,
        },
    )
    assert payload["kind"] == "single_note"
    assert payload["summary"] == "Detected A4."


def test_register_music_tools_is_idempotent() -> None:
    live_tools.register_music_tools()
    live_tools.register_music_tools()
