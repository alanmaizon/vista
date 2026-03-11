"""Deterministic live-tool routing for Eurydice music sessions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from .api import (
    MusicLessonActionRequest,
    MusicLessonStepRequest,
    next_guided_lesson_step,
    render_stored_music_score,
    run_guided_lesson_action,
)
from ...tools import ToolError, ToolSpec, tool_registry


LIVE_MUSIC_TOOL_SPECS: tuple[dict[str, str], ...] = (
    {
        "name": "lesson_action",
        "description": (
            "Unified guided lesson action. Use this to prepare a score, advance a bar, or compare a take."
        ),
    },
    {
        "name": "lesson_step",
        "description": "Return the next guided lesson step for a prepared score.",
    },
    {
        "name": "render_score",
        "description": "Return notation render payload for a prepared score.",
    },
)


class LiveMusicToolError(Exception):
    """Raised when a live music tool call cannot be executed."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class _LessonActionToolArgs(MusicLessonActionRequest):
    model_config = ConfigDict(extra="forbid")


class _LessonStepToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_id: UUID
    current_measure_index: int | None = None
    lesson_stage: str = "idle"


class _RenderScoreToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_id: UUID


def music_live_tool_prompt_fragment() -> str:
    """Prompt fragment instructing Gemini how to request deterministic tools."""
    return (
        "If you need deterministic score/lesson data, request a tool call by emitting exactly one line:\n"
        'TOOL_CALL: {"name":"lesson_action","args":{...}}\n'
        "Supported tool names: lesson_action, lesson_step, render_score.\n"
        "Do not include extra prose in a TOOL_CALL line."
    )


def _normalize_tool_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise LiveMusicToolError("tool name is required.")
    return name.strip().lower()


async def run_live_music_tool(
    db: AsyncSession,
    *,
    user_id: str,
    tool_name: str,
    args: dict[str, Any] | None,
) -> dict[str, Any]:
    """Execute a deterministic music tool call in the current auth scope."""
    normalized_name = _normalize_tool_name(tool_name)
    payload = args or {}
    current_user = {"uid": user_id}

    try:
        if normalized_name == "lesson_action":
            request = _LessonActionToolArgs.model_validate(payload)
            result = await run_guided_lesson_action(request, current_user=current_user, db=db)
            return result.model_dump(mode="json")

        if normalized_name == "lesson_step":
            request = _LessonStepToolArgs.model_validate(payload)
            request = MusicLessonStepRequest.model_validate(
                {
                    "current_measure_index": request.current_measure_index,
                    "lesson_stage": request.lesson_stage,
                }
            )
            result = await next_guided_lesson_step(
                request.score_id,
                request,
                current_user=current_user,
                db=db,
            )
            return result.model_dump(mode="json")

        if normalized_name == "render_score":
            request = _RenderScoreToolArgs.model_validate(payload)
            result = await render_stored_music_score(
                request.score_id,
                current_user=current_user,
                db=db,
            )
            return result.model_dump(mode="json")
    except ValidationError as exc:
        raise LiveMusicToolError(exc.errors()[0].get("msg", "Invalid tool arguments.")) from exc
    except HTTPException as exc:
        raise LiveMusicToolError(str(exc.detail), status_code=exc.status_code) from exc

    available = ", ".join(spec["name"] for spec in LIVE_MUSIC_TOOL_SPECS)
    raise LiveMusicToolError(f"Unsupported tool '{normalized_name}'. Supported tools: {available}.")


def register_music_tools() -> None:
    """Register all music tools into the global tool_registry."""

    async def _execute_lesson_action(
        db: AsyncSession, user_id: str, args: _LessonActionToolArgs
    ) -> dict[str, Any]:
        current_user = {"uid": user_id}
        try:
            result = await run_guided_lesson_action(args, current_user=current_user, db=db)
            return result.model_dump(mode="json")
        except HTTPException as exc:
            raise ToolError(str(exc.detail), status_code=exc.status_code) from exc

    async def _execute_lesson_step(
        db: AsyncSession, user_id: str, args: _LessonStepToolArgs
    ) -> dict[str, Any]:
        current_user = {"uid": user_id}
        step_request = MusicLessonStepRequest.model_validate(
            {
                "current_measure_index": args.current_measure_index,
                "lesson_stage": args.lesson_stage,
            }
        )
        try:
            result = await next_guided_lesson_step(
                args.score_id,
                step_request,
                current_user=current_user,
                db=db,
            )
            return result.model_dump(mode="json")
        except HTTPException as exc:
            raise ToolError(str(exc.detail), status_code=exc.status_code) from exc

    async def _execute_render_score(
        db: AsyncSession, user_id: str, args: _RenderScoreToolArgs
    ) -> dict[str, Any]:
        current_user = {"uid": user_id}
        try:
            result = await render_stored_music_score(
                args.score_id,
                current_user=current_user,
                db=db,
            )
            return result.model_dump(mode="json")
        except HTTPException as exc:
            raise ToolError(str(exc.detail), status_code=exc.status_code) from exc

    tool_registry.register(
        ToolSpec(
            name="lesson_action",
            description=(
                "Unified guided lesson action. Use this to prepare a score, advance a bar, or compare a take."
            ),
            args_schema=_LessonActionToolArgs,
            executor=_execute_lesson_action,
        )
    )
    tool_registry.register(
        ToolSpec(
            name="lesson_step",
            description="Return the next guided lesson step for a prepared score.",
            args_schema=_LessonStepToolArgs,
            executor=_execute_lesson_step,
        )
    )
    tool_registry.register(
        ToolSpec(
            name="render_score",
            description="Return notation render payload for a prepared score.",
            args_schema=_RenderScoreToolArgs,
            executor=_execute_render_score,
            is_cacheable=True,
        )
    )
