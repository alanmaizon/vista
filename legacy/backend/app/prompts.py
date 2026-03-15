"""Centralized prompt composition for Eurydice."""

from __future__ import annotations

from functools import lru_cache

from .domains import SessionRuntime
from .domains.music.live_tools import music_live_tool_prompt_fragment
from .settings import settings


@lru_cache(maxsize=8)
def _stable_prompt_scaffold(
    *,
    base_system_prompt: str,
    skill_instructions: str,
    tool_prompt: str,
) -> str:
    sections = [
        base_system_prompt.strip(),
        "Tutor policy:",
        "- Begin with a short welcome and one clear next step.",
        "- Prefer teaching over control-panel narration.",
        "- Keep each turn focused on one correction, one question, or one micro-exercise.",
        "- Distinguish observed evidence from inference and uncertainty.",
        "- Never fabricate pitch/rhythm claims without deterministic evidence.",
        "- If a deterministic tool is required, call it instead of guessing.",
        "- Keep responses concise while streaming; refine after new evidence arrives.",
    ]
    if skill_instructions:
        sections.extend(["Skill policy:", skill_instructions.strip()])
    if tool_prompt:
        sections.extend(["Tool policy:", tool_prompt.strip()])
    return "\n".join(section for section in sections if section).strip()


class PromptComposer:
    """Builds prompts for a live session from multiple sources."""

    def __init__(
        self,
        runtime: SessionRuntime,
        live_context: str,
        memory_context: str = "",
    ):
        """Initialise the composer with session-specific context."""
        self.runtime = runtime
        self.live_context = live_context
        self.memory_context = memory_context

    def get_system_prompt(self) -> str:
        """Build the full system prompt for the Gemini Live session."""
        base_system_prompt = self.runtime.system_prompt(
            settings.system_instructions,
            settings.music_system_instructions,
        )
        skill_instructions = ""
        if hasattr(self.runtime, "skill_instructions"):
            skill_instructions = str(self.runtime.skill_instructions() or "").strip()
        tool_prompt = music_live_tool_prompt_fragment()
        scaffold = _stable_prompt_scaffold(
            base_system_prompt=base_system_prompt,
            skill_instructions=skill_instructions,
            tool_prompt=tool_prompt,
        )

        context_parts: list[str] = []
        if self.live_context:
            context_parts.append(f"Retrieved session context:\n{self.live_context}")
        if self.memory_context:
            context_parts.append(f"Retrieved musical memories:\n{self.memory_context}")

        if context_parts:
            combined = "\n\n".join(context_parts)
            return (
                f"{scaffold}\n\n"
                f"{combined}\n\n"
                "Use this context as supporting memory only. Prioritize current live evidence. "
                "When uncertain or conflicting, request replay/reframing before concluding."
            )
        return scaffold

    def get_opening_user_prompt(self) -> str | None:
        """Return the opening user-role prompt, if the runtime requires one."""
        if self.runtime.uses_model_opening_prompt():
            return self.runtime.opening_prompt()
        return None
