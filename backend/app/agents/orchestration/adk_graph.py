"""ADK-backed policy graph for live turn orchestration."""

from __future__ import annotations

import importlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from ...settings import Settings
from .contracts import TurnPlan, TurnPolicyContext
from .policy_engine import TurnPolicyEngine

logger = logging.getLogger("ancient_greek.orchestration")

_ALLOWED_TOOLS = {"parse_passage", "grade_attempt", "generate_drill"}
_ALLOWED_STAGES = {"tool_preflight", "direct_generation"}

_INTENT_AGENT_INSTRUCTION = """You classify learner-turn intent for an Ancient Greek tutor.
Output one short JSON object with:
{
  "intent": "morphology_help" | "translation_check" | "drill_request" | "general_guidance",
  "confidence": "low" | "medium" | "high",
  "signals": ["brief evidence strings"]
}
Return JSON only.
"""

_POLICY_AGENT_INSTRUCTION = """You are the turn-policy planner for an Ancient Greek live tutor.
Decide the next orchestration stage using only the given context.

Rules:
- Use "tool_preflight" when deterministic grounding should happen first.
- Use "direct_generation" when model generation can proceed immediately.
- If you choose "tool_preflight", preflight_tool_name must be one of:
  parse_passage, grade_attempt, generate_drill.
- preflight_tool_arguments must match the chosen tool.
- Keep rationale short and operational.

Return JSON only in this schema:
{
  "stage": "tool_preflight" | "direct_generation",
  "rationale": "short rationale",
  "preflight_tool_name": "parse_passage" | "grade_attempt" | "generate_drill" | null,
  "preflight_tool_arguments": { ... }
}
"""


@dataclass
class _AdkSymbols:
    agent_cls: type
    sequential_agent_cls: type
    runner_cls: type
    session_service_cls: type
    content_cls: type
    part_cls: type


class AdkTurnPolicyGraph:
    """Executes turn planning through an ADK graph, with deterministic fallback."""

    def __init__(self, settings: Settings, fallback_policy: TurnPolicyEngine) -> None:
        self._settings = settings
        self._fallback_policy = fallback_policy
        self._symbols: _AdkSymbols | None = None
        self._runner: Any | None = None
        self._session_service: Any | None = None

    async def plan_turn(self, context: TurnPolicyContext) -> TurnPlan:
        if not self._settings.use_google_adk:
            return self._fallback_with_reason(context, "TUTOR_USE_GOOGLE_ADK is false.")

        symbols = self._load_symbols()
        if symbols is None:
            return self._fallback_with_reason(
                context,
                "google-adk package is unavailable in this environment.",
            )

        if not self._credentials_ready():
            return self._fallback_with_reason(
                context,
                "No Gemini/Google credentials were detected for ADK model calls.",
            )

        if not self._ensure_graph(symbols):
            return self._fallback_with_reason(
                context,
                "ADK graph could not be initialized with the installed library version.",
            )

        try:
            return await self._run_graph(context)
        except Exception as exc:
            logger.warning("ADK policy graph failed for turn %s: %s", context.turn_input.turn_id, exc)
            return self._fallback_with_reason(context, f"ADK graph execution failed: {exc}")

    def _fallback_with_reason(self, context: TurnPolicyContext, reason: str) -> TurnPlan:
        fallback = self._fallback_policy.choose(context)
        return TurnPlan(
            engine=fallback.engine,
            stage=fallback.stage,
            rationale=f"{fallback.rationale} ADK fallback: {reason}",
            preflight_tool_name=fallback.preflight_tool_name,
            preflight_tool_arguments=fallback.preflight_tool_arguments,
        )

    def _load_symbols(self) -> _AdkSymbols | None:
        if self._symbols is not None:
            return self._symbols

        try:
            importlib.import_module("google.adk")
            agents_module = importlib.import_module("google.adk.agents")
            runners_module = importlib.import_module("google.adk.runners")
            sessions_module = importlib.import_module("google.adk.sessions")
            genai_types = importlib.import_module("google.genai.types")
        except ImportError:
            return None

        agent_cls = getattr(agents_module, "Agent", None) or getattr(agents_module, "LlmAgent", None)
        sequential_agent_cls = getattr(agents_module, "SequentialAgent", None)
        runner_cls = getattr(runners_module, "Runner", None)
        session_service_cls = getattr(sessions_module, "InMemorySessionService", None)
        content_cls = getattr(genai_types, "Content", None)
        part_cls = getattr(genai_types, "Part", None)

        required = [
            agent_cls,
            sequential_agent_cls,
            runner_cls,
            session_service_cls,
            content_cls,
            part_cls,
        ]
        if any(value is None for value in required):
            return None

        self._symbols = _AdkSymbols(
            agent_cls=agent_cls,
            sequential_agent_cls=sequential_agent_cls,
            runner_cls=runner_cls,
            session_service_cls=session_service_cls,
            content_cls=content_cls,
            part_cls=part_cls,
        )
        return self._symbols

    def _credentials_ready(self) -> bool:
        api_key_present = bool(
            self._settings.gemini_api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        vertex_ready = bool(self._settings.google_cloud_project)
        return api_key_present or vertex_ready

    def _ensure_graph(self, symbols: _AdkSymbols) -> bool:
        if self._runner is not None:
            return True

        agent_cls = symbols.agent_cls
        sequential_cls = symbols.sequential_agent_cls
        runner_cls = symbols.runner_cls
        session_service_cls = symbols.session_service_cls

        try:
            intent_agent = self._construct_agent(
                agent_cls,
                name="TurnIntentClassifier",
                instruction=_INTENT_AGENT_INSTRUCTION,
            )
            policy_agent = self._construct_agent(
                agent_cls,
                name="TurnPolicyPlanner",
                instruction=_POLICY_AGENT_INSTRUCTION,
            )
            graph_agent = self._construct_sequential_agent(
                sequential_cls,
                name="TurnPolicyGraph",
                sub_agents=[intent_agent, policy_agent],
            )
            self._session_service = session_service_cls()
            self._runner = self._construct_runner(
                runner_cls,
                agent=graph_agent,
                session_service=self._session_service,
            )
            return True
        except Exception as exc:
            logger.warning("Unable to initialize ADK graph runtime: %s", exc)
            self._runner = None
            self._session_service = None
            return False

    def _construct_agent(self, agent_cls: type, *, name: str, instruction: str) -> Any:
        attempts = [
            {
                "name": name,
                "model": self._settings.gemini_response_model,
                "instruction": instruction,
            },
            {
                "name": name,
                "model": self._settings.gemini_response_model,
                "instructions": instruction,
            },
        ]
        for kwargs in attempts:
            try:
                return agent_cls(**kwargs)
            except TypeError:
                continue
        raise TypeError(f"Could not construct ADK Agent '{name}' with known signatures.")

    def _construct_sequential_agent(
        self,
        sequential_cls: type,
        *,
        name: str,
        sub_agents: list[Any],
    ) -> Any:
        attempts = [
            {"name": name, "sub_agents": sub_agents},
            {"name": name, "agents": sub_agents},
        ]
        for kwargs in attempts:
            try:
                return sequential_cls(**kwargs)
            except TypeError:
                continue
        raise TypeError("Could not construct ADK SequentialAgent with known signatures.")

    def _construct_runner(self, runner_cls: type, *, agent: Any, session_service: Any) -> Any:
        attempts = [
            {
                "agent": agent,
                "app_name": "ancient-greek-live-tutor",
                "session_service": session_service,
                "auto_create_session": True,
            },
            {
                "agent": agent,
                "app_name": "ancient-greek-live-tutor",
                "session_service": session_service,
            },
        ]
        for kwargs in attempts:
            try:
                return runner_cls(**kwargs)
            except TypeError:
                continue
        raise TypeError("Could not construct ADK Runner with known signatures.")

    async def _run_graph(self, context: TurnPolicyContext) -> TurnPlan:
        if self._runner is None:
            raise RuntimeError("ADK runner has not been initialized.")

        content = self._build_content(context)
        user_id = "live-orchestration"
        session_id = f"turn-policy-{context.turn_input.turn_id}"
        final_text: str | None = None

        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            candidate = self._extract_text_from_event(event)
            if not candidate:
                continue
            if self._is_final_response(event):
                final_text = candidate
            elif final_text is None:
                final_text = candidate

        if not final_text:
            raise RuntimeError("ADK graph returned no policy text.")

        parsed = self._parse_policy_json(final_text)
        return TurnPlan(
            engine="google-adk",
            stage=parsed["stage"],
            rationale=parsed["rationale"],
            preflight_tool_name=parsed["preflight_tool_name"],
            preflight_tool_arguments=parsed["preflight_tool_arguments"],
        )

    def _build_content(self, context: TurnPolicyContext) -> Any:
        symbols = self._symbols
        if symbols is None:
            raise RuntimeError("ADK symbols are not loaded.")

        payload = {
            "mode": context.mode.value,
            "turn_id": context.turn_input.turn_id,
            "turn_end_reason": context.turn_input.reason,
            "target_text": context.target_text,
            "preferred_response_language": context.preferred_response_language,
            "learner_text": context.turn_input.learner_text,
            "audio_chunk_count": context.turn_input.audio_chunk_count,
            "image_frame_count": context.turn_input.image_frame_count,
            "available_tools": sorted(_ALLOWED_TOOLS),
        }
        prompt = (
            "Plan the next orchestration action for this learner turn.\n"
            "Context JSON:\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )
        return symbols.content_cls(role="user", parts=[symbols.part_cls(text=prompt)])

    def _extract_text_from_event(self, event: Any) -> str | None:
        content = getattr(event, "content", None)
        if content is None:
            return None
        parts = getattr(content, "parts", None) or []
        texts = [str(part.text).strip() for part in parts if getattr(part, "text", None)]
        if not texts:
            return None
        return "\n".join(texts)

    def _is_final_response(self, event: Any) -> bool:
        is_final_response = getattr(event, "is_final_response", None)
        if callable(is_final_response):
            try:
                return bool(is_final_response())
            except Exception:
                return False
        return bool(getattr(event, "final", False))

    def _parse_policy_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        payload: dict[str, Any]
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("Policy response was not valid JSON.")
            payload = json.loads(text[start : end + 1])

        stage = payload.get("stage")
        if stage not in _ALLOWED_STAGES:
            raise ValueError(f"Unsupported stage '{stage}'.")

        preflight_tool_name = payload.get("preflight_tool_name")
        if preflight_tool_name in ("", "null"):
            preflight_tool_name = None

        if stage == "tool_preflight":
            if not isinstance(preflight_tool_name, str) or preflight_tool_name not in _ALLOWED_TOOLS:
                raise ValueError("tool_preflight stage requires a supported preflight tool.")
        else:
            preflight_tool_name = None

        preflight_tool_arguments = payload.get("preflight_tool_arguments", {})
        if preflight_tool_name is None:
            preflight_tool_arguments = {}
        elif not isinstance(preflight_tool_arguments, dict):
            raise ValueError("preflight_tool_arguments must be an object when a tool is selected.")

        rationale = str(payload.get("rationale", "")).strip() or "ADK policy graph selected next action."
        return {
            "stage": stage,
            "rationale": rationale,
            "preflight_tool_name": preflight_tool_name,
            "preflight_tool_arguments": preflight_tool_arguments,
        }
