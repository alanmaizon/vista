"""Centralized prompt composition for Eurydice."""

from __future__ import annotations

from .domains import SessionRuntime
from .domains.music.live_tools import music_live_tool_prompt_fragment
from .settings import settings


class PromptComposer:
    """Builds prompts for a live session from multiple sources."""

    def __init__(self, runtime: SessionRuntime, live_context: str):
        """Initialise the composer with session-specific context."""
        self.runtime = runtime
        self.live_context = live_context

    def get_system_prompt(self) -> str:
        """Build the full system prompt for the Gemini Live session."""
        base_system_prompt = self.runtime.system_prompt(
            settings.system_instructions,
            settings.music_system_instructions,
        )
        tool_prompt = music_live_tool_prompt_fragment()
        if tool_prompt:
            base_system_prompt = f"{base_system_prompt}\n\n{tool_prompt}"

        if self.live_context:
            return (
                f"{base_system_prompt}\n\n"
                "Retrieved session context:\n"
                f"{self.live_context}\n\n"
                "Use this context as supporting memory only. Prioritize current live evidence. "
                "When uncertain or conflicting, request replay/reframing before concluding."
            )
        return base_system_prompt

    def get_opening_user_prompt(self) -> str | None:
        """Return the opening user-role prompt, if the runtime requires one."""
        if self.runtime.uses_model_opening_prompt():
            return self.runtime.opening_prompt()
        return None