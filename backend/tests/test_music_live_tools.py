from __future__ import annotations

import uuid

import pytest

from app.domains.music import live_tools


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
