"""Live turn orchestrator with ADK graph first, deterministic fallback second."""

from __future__ import annotations

from ...schemas import TutorMode
from ...settings import Settings
from .adk_graph import AdkTurnPolicyGraph
from .contracts import LiveTurnInput, TurnPlan, TurnPolicyContext
from .policy_engine import TurnPolicyEngine


class LiveTurnOrchestrator:
    """Produces a turn plan and first action for a learner turn."""

    def __init__(
        self,
        settings: Settings,
        *,
        fallback_policy: TurnPolicyEngine | None = None,
        adk_graph: AdkTurnPolicyGraph | None = None,
    ) -> None:
        self._settings = settings
        self._fallback_policy = fallback_policy or TurnPolicyEngine()
        self._adk_graph = adk_graph or AdkTurnPolicyGraph(settings, self._fallback_policy)

    async def plan_turn(
        self,
        *,
        mode: TutorMode,
        target_text: str | None,
        preferred_response_language: str,
        turn_input: LiveTurnInput,
    ) -> TurnPlan:
        context = TurnPolicyContext(
            mode=mode,
            target_text=target_text,
            preferred_response_language=preferred_response_language,
            turn_input=turn_input,
        )
        return await self._adk_graph.plan_turn(context)


__all__ = ["LiveTurnInput", "LiveTurnOrchestrator", "TurnPlan"]
