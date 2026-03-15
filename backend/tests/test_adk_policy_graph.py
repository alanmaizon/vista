import asyncio

from backend.app.agents.orchestration.adk_graph import AdkTurnPolicyGraph
from backend.app.agents.orchestration.contracts import LiveTurnInput, TurnPlan, TurnPolicyContext
from backend.app.agents.orchestration.live_turns import LiveTurnOrchestrator
from backend.app.agents.orchestration.policy_engine import TurnPolicyEngine
from backend.app.schemas import TutorMode
from backend.app.settings import Settings


def _context(*, mode: TutorMode, learner_text: str, target_text: str | None) -> TurnPolicyContext:
    return TurnPolicyContext(
        mode=mode,
        target_text=target_text,
        preferred_response_language="English",
        turn_input=LiveTurnInput(
            turn_id="turn-test",
            reason="done",
            learner_text=learner_text,
            audio_chunk_count=0,
            image_frame_count=0,
        ),
    )


def test_adk_graph_falls_back_when_disabled() -> None:
    settings = Settings(use_google_adk=False)
    graph = AdkTurnPolicyGraph(settings, TurnPolicyEngine())
    plan = asyncio.run(
        graph.plan_turn(
            _context(
                mode=TutorMode.morphology_coach,
                learner_text="please parse logos",
                target_text="logos gar didaskalos",
            )
        )
    )
    assert plan.engine == "heuristic-fallback"
    assert plan.preflight_tool_name == "parse_passage"
    assert "ADK fallback: TUTOR_USE_GOOGLE_ADK is false." in plan.rationale


def test_parse_policy_json_normalizes_direct_generation_payload() -> None:
    graph = AdkTurnPolicyGraph(Settings(), TurnPolicyEngine())
    parsed = graph._parse_policy_json(  # noqa: SLF001
        """
        {
          "stage": "direct_generation",
          "rationale": "Proceed directly.",
          "preflight_tool_name": "parse_passage",
          "preflight_tool_arguments": {"text": "ignored"}
        }
        """
    )
    assert parsed["stage"] == "direct_generation"
    assert parsed["preflight_tool_name"] is None
    assert parsed["preflight_tool_arguments"] == {}


def test_live_turn_orchestrator_can_use_injected_adk_graph() -> None:
    class StubGraph:
        async def plan_turn(self, context: TurnPolicyContext) -> TurnPlan:
            assert context.mode == TutorMode.guided_reading
            return TurnPlan(
                engine="google-adk",
                stage="tool_preflight",
                rationale="Stub ADK graph selected parse_passage.",
                preflight_tool_name="parse_passage",
                preflight_tool_arguments={"text": "logos"},
            )

    orchestrator = LiveTurnOrchestrator(Settings(), adk_graph=StubGraph())  # type: ignore[arg-type]
    plan = asyncio.run(
        orchestrator.plan_turn(
            mode=TutorMode.guided_reading,
            target_text="logos",
            preferred_response_language="English",
            turn_input=LiveTurnInput(turn_id="turn-graph", reason="done", learner_text="parse logos"),
        )
    )
    assert plan.engine == "google-adk"
    assert plan.preflight_tool_name == "parse_passage"
