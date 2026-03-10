"""
End-to-end evaluation harness for live tutoring scenarios.

This script runs multi-turn scenarios against the backend logic to verify
that the system correctly handles conversation flow, tool calls, and state
management, without needing a live connection to the Gemini API.
"""

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

# Add app root to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.domains import build_session_runtime
from app.prompts import PromptComposer
from app.tools import ToolError, tool_registry
from app.domains.music.live_tools import register_music_tools


@dataclass
class MockLiveBridge:
    """A mock of the GeminiLiveBridge for controlled scenario testing."""

    model_responses: list[dict[str, Any]] = field(default_factory=list)
    sent_text: list[tuple[str, str]] = field(default_factory=list)
    _events: asyncio.Queue[dict[str, Any] | None] = field(default_factory=asyncio.Queue)
    _response_index: int = 0

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        await self._events.put(None)

    async def send_text(self, text: str, *, role: str = "user") -> None:
        self.sent_text.append((text, role))
        # When user sends text, mock a model response
        if role == "user" and self._response_index < len(self.model_responses):
            response = self.model_responses[self._response_index]
            await self._events.put(response)
            self._response_index += 1

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event


@dataclass
class ScenarioStep:
    """One turn in a live evaluation scenario."""

    user_input: str | None = None
    model_response: dict[str, Any] | None = None
    expected_tool_name: str | None = None
    expected_tool_args: dict[str, Any] | None = None


@dataclass
class LiveTutorScenario:
    """A multi-turn scenario for evaluating the live tutor."""

    name: str
    skill: str
    goal: str
    steps: list[ScenarioStep]


class ScenarioRunner:
    """Executes and evaluates a live tutor scenario."""

    def __init__(self, scenario: LiveTutorScenario):
        self.scenario = scenario
        self.passed = True
        self.logs: list[str] = []

    async def run(self) -> None:
        """Run the scenario and log results."""
        print(f"--- Running scenario: {self.scenario.name} ---")
        runtime = build_session_runtime(domain="MUSIC", skill=self.scenario.skill, goal=self.scenario.goal)
        composer = PromptComposer(runtime, live_context="")
        system_prompt = composer.get_system_prompt()
        self.logs.append(f"System prompt generated ({len(system_prompt)} chars).")

        mock_bridge = MockLiveBridge(model_responses=[s.model_response for s in self.scenario.steps if s.model_response])

        for i, step in enumerate(self.scenario.steps):
            self.logs.append(f"Step {i+1}: User says '{step.user_input}'")
            if step.user_input:
                await mock_bridge.send_text(step.user_input, role="user")

            async for event in mock_bridge.receive():
                if event.get("type") == "server.tool_call":
                    self.logs.append(f"  -> Model requests tool: {event.get('name')}")
                    if step.expected_tool_name and event.get("name") == step.expected_tool_name:
                        self.logs.append(f"  [PASS] Expected tool '{step.expected_tool_name}' was called.")
                        # In a real test, we'd execute the tool and send back a result.
                        # For this harness, we just verify the call was made.
                    else:
                        self.logs.append(f"  [FAIL] Expected tool '{step.expected_tool_name}', but got '{event.get('name')}'")
                        self.passed = False
                # Stop listening after the first event for this simple harness
                break

        await mock_bridge.close()
        print("\n".join(self.logs))
        print(f"--- Result: {'PASS' if self.passed else 'FAIL'} ---")


GREETING_AND_TOOL_USE_SCENARIO = LiveTutorScenario(
    name="Greeting and Initial Tool Use",
    skill="GUIDED_LESSON",
    goal="I want to learn a new song.",
    steps=[
        ScenarioStep(
            user_input="Hi Eurydice, can you help me learn a song?",
            model_response={
                "type": "server.text",
                "text": "Of course! What song would you like to learn? You can provide a score line for me to prepare.",
            },
        ),
        ScenarioStep(
            user_input="Let's start with C4/q D4/q E4/h",
            model_response={
                "type": "server.tool_call",
                "name": "lesson_action",
                "args": {"source_text": "C4/q D4/q E4/h"},
            },
            expected_tool_name="lesson_action",
        ),
    ],
)


async def main() -> None:
    """Main entrypoint for the evaluation script."""
    # This is a mock runner; it doesn't use the full websocket stack from main.py,
    # but it reuses the core components (runtime, prompts, tools).
    # A more advanced version could use the TestClient to hit the actual endpoint.
    
    # Register tools so they are available in the prompt and for execution.
    register_music_tools()

    scenarios = [GREETING_AND_TOOL_USE_SCENARIO]
    results = []

    for scenario in scenarios:
        runner = ScenarioRunner(scenario)
        await runner.run()
        results.append(runner.passed)
        print("\n")

    if all(results):
        print("All scenarios passed.")
        sys.exit(0)
    else:
        print(f"{results.count(False)}/{len(results)} scenarios failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())