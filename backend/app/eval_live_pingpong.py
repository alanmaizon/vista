"""Deterministic ping-pong evaluation for the reset Eurydice Live backend.

This evaluator drives the active `/ws/live` contract through the FastAPI app
using a fake live bridge. It grades:

- prompt biasing for piece names and bystander handling
- transcript propagation through the reset websocket path
- time from `client.audio_end` to first assistant response
- time to first assistant audio
- time to assistant turn completion
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
import sys
from typing import Any

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import main as main_module
from app.live_agent.prompts import build_opening_user_prompt, build_system_prompt
from app.live_agent.schemas import LiveSessionProfile


@dataclass(frozen=True)
class PingPongScenario:
    key: str
    title: str
    profile: LiveSessionProfile
    audio_chunk_count: int
    user_transcript_final: str
    assistant_transcript: str
    assistant_text: str
    transcript_delay_ms: int
    audio_delay_ms: int
    completion_delay_ms: int
    prompt_markers: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioGrade:
    prompt_biasing: float
    transcript_propagation: float
    first_response_latency: float
    first_audio_latency: float
    full_turn_latency: float
    turn_completion: float

    @property
    def overall(self) -> float:
        return round(
            mean(
                [
                    self.prompt_biasing,
                    self.transcript_propagation,
                    self.first_response_latency,
                    self.first_audio_latency,
                    self.full_turn_latency,
                    self.turn_completion,
                ]
            ),
            3,
        )


SCENARIOS: tuple[PingPongScenario, ...] = (
    PingPongScenario(
        key="canonical_piece_bias",
        title="Canonical piece bias for uncommon tune title",
        profile=LiveSessionProfile(
            mode="music_tutor",
            instrument="Fiddle",
            piece="Shoe the Donkey",
            goal="learn the first phrase",
            camera_expected=False,
        ),
        audio_chunk_count=6,
        user_transcript_final="learn irish tune called shoe the donkey",
        assistant_transcript='"Shoe the Donkey" sounds good.',
        assistant_text='"Shoe the Donkey" sounds good. Do you want to learn it by ear or from the score?',
        transcript_delay_ms=120,
        audio_delay_ms=190,
        completion_delay_ms=320,
        prompt_markers=("Piece: Shoe the Donkey.", "treat that title as canonical", "proper noun"),
    ),
    PingPongScenario(
        key="bystander_recovery",
        title="Reject bystander speech and ask for a music restatement",
        profile=LiveSessionProfile(
            mode="music_tutor",
            instrument="Voice",
            piece="",
            goal="work on diction",
            camera_expected=True,
        ),
        audio_chunk_count=5,
        user_transcript_final="my wife is dropping off food",
        assistant_transcript="Could you restate the music question?",
        assistant_text="I may have caught background speech. Could you restate the music question or show the score?",
        transcript_delay_ms=140,
        audio_delay_ms=230,
        completion_delay_ms=360,
        prompt_markers=("bystander speech", "restate the musical question", "show the score again"),
    ),
)


class _PingPongFakeBridge:
    scenario_queue: list[PingPongScenario] = []

    def __init__(self, **kwargs: Any) -> None:
        self.model_id = kwargs["model_id"]
        self.active_location = kwargs["location"]
        self.using_adk = False
        self.system_prompt = kwargs["system_prompt"]
        self.sent_text: list[tuple[str, str]] = []
        self.sent_audio: list[bytes] = []
        self.audio_end_calls = 0
        self.closed = False
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._scenario = type(self).scenario_queue.pop(0)

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        self.closed = True
        await self._events.put(None)

    async def send_audio(self, payload: bytes) -> None:
        self.sent_audio.append(payload)

    async def send_audio_end(self) -> None:
        self.audio_end_calls += 1
        asyncio.create_task(self._emit_turn())

    async def send_image_jpeg(self, payload: bytes) -> None:
        return None

    async def send_text(self, text: str, *, role: str = "user") -> None:
        self.sent_text.append((text, role))

    async def receive(self):
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def _emit_turn(self) -> None:
        scenario = self._scenario
        await self._events.put(
            {
                "type": "server.transcript",
                "role": "user",
                "text": scenario.user_transcript_final,
                "partial": False,
                "turn_id": "user-1",
                "chunk_index": 0,
                "turn_complete": True,
            }
        )
        await asyncio.sleep(scenario.transcript_delay_ms / 1000)
        await self._events.put(
            {
                "type": "server.transcript",
                "role": "assistant",
                "text": scenario.assistant_transcript,
                "partial": False,
                "turn_id": "assistant-1",
                "chunk_index": 0,
                "turn_complete": False,
            }
        )
        await asyncio.sleep(max(0, scenario.audio_delay_ms - scenario.transcript_delay_ms) / 1000)
        await self._events.put(
            {
                "type": "server.audio",
                "data_b64": "AAAA",
                "mime": "audio/pcm;rate=24000",
                "turn_id": "assistant-1",
                "chunk_index": 1,
                "turn_complete": False,
            }
        )
        await asyncio.sleep(max(0, scenario.completion_delay_ms - scenario.audio_delay_ms) / 1000)
        await self._events.put(
            {
                "type": "server.text",
                "text": scenario.assistant_text,
                "turn_id": "assistant-1",
                "chunk_index": 2,
                "turn_complete": True,
            }
        )


def _score_latency(value_ms: int | None, *, target_ms: int, fail_ms: int) -> float:
    if value_ms is None:
        return 0.0
    if value_ms <= target_ms:
        return 1.0
    if value_ms >= fail_ms:
        return 0.0
    span = fail_ms - target_ms
    return round(max(0.0, 1 - ((value_ms - target_ms) / span)), 3)


def _turn_from_debug(debug_payload: dict[str, Any], session_id: str) -> dict[str, Any]:
    sessions = list(debug_payload.get("recent_sessions") or []) + list(debug_payload.get("active_sessions") or [])
    for session in sessions:
        if session.get("session_id") != session_id:
            continue
        recent_turns = (((session.get("pingpong") or {}).get("recent_turns")) or [])
        if recent_turns:
            return dict(recent_turns[0])
    raise AssertionError(f"No pingpong turn found for session {session_id}")


@contextmanager
def _patched_client() -> Any:
    original_bridge = main_module.GeminiLiveBridge
    original_adk_status = main_module.adk_runtime_status
    original_registry = main_module.runtime_registry
    try:
        _PingPongFakeBridge.scenario_queue = []
        main_module.GeminiLiveBridge = _PingPongFakeBridge
        main_module.adk_runtime_status = lambda: (False, "pingpong-eval")
        main_module.runtime_registry = main_module.LiveRuntimeRegistry()
        with TestClient(main_module.app) as client:
            yield client
    finally:
        main_module.GeminiLiveBridge = original_bridge
        main_module.adk_runtime_status = original_adk_status
        main_module.runtime_registry = original_registry


def _grade_scenario(client: TestClient, scenario: PingPongScenario) -> dict[str, Any]:
    _PingPongFakeBridge.scenario_queue.append(scenario)
    with client.websocket_connect("/ws/live") as ws:
        init_payload = {"type": "client.init", **scenario.profile.model_dump(mode="json")}
        ws.send_json(init_payload)
        status_event = ws.receive_json()
        session_id = str(status_event["session_id"])
        for _ in range(scenario.audio_chunk_count):
            ws.send_json({"type": "client.audio", "mime": "audio/pcm;rate=16000", "data_b64": "AA=="})
        ws.send_json({"type": "client.audio_end"})

        received_events: list[dict[str, Any]] = []
        while True:
            event = ws.receive_json()
            received_events.append(event)
            if event.get("type") == "server.text" and event.get("turn_complete"):
                break

        ws.send_json({"type": "client.stop"})
        _ = ws.receive_json()

    debug_payload = client.get("/api/runtime/debug").json()
    turn = _turn_from_debug(debug_payload, session_id)

    system_prompt = build_system_prompt(scenario.profile)
    opening_prompt = build_opening_user_prompt(scenario.profile)
    prompt_biasing = round(
        sum(1 for marker in scenario.prompt_markers if marker in system_prompt or marker in opening_prompt)
        / len(scenario.prompt_markers),
        3,
    )
    transcript_propagation = 1.0 if turn.get("user_transcript_final") == scenario.user_transcript_final else 0.0
    grade = ScenarioGrade(
        prompt_biasing=prompt_biasing,
        transcript_propagation=transcript_propagation,
        first_response_latency=_score_latency(turn.get("first_response_ms"), target_ms=400, fail_ms=2000),
        first_audio_latency=_score_latency(turn.get("first_audio_ms"), target_ms=700, fail_ms=2500),
        full_turn_latency=_score_latency(turn.get("full_turn_ms"), target_ms=1400, fail_ms=4000),
        turn_completion=1.0 if turn.get("status") == "completed" else 0.0,
    )
    return {
        "scenario": scenario.profile.model_dump(mode="json") | {"key": scenario.key, "title": scenario.title},
        "status_event": status_event,
        "received_event_types": [str(event.get("type", "")) for event in received_events],
        "prompt_markers": list(scenario.prompt_markers),
        "turn": turn,
        "grade": asdict(grade) | {"overall": grade.overall},
    }


def run_eval() -> dict[str, Any]:
    scenario_reports: list[dict[str, Any]] = []
    with _patched_client() as client:
        for scenario in SCENARIOS:
            scenario_reports.append(_grade_scenario(client, scenario))

    rubric_keys = (
        "prompt_biasing",
        "transcript_propagation",
        "first_response_latency",
        "first_audio_latency",
        "full_turn_latency",
        "turn_completion",
    )
    rubric = {
        key: round(mean(float(report["grade"][key]) for report in scenario_reports), 3)
        for key in rubric_keys
    }
    aggregate_score = round(mean(float(report["grade"]["overall"]) for report in scenario_reports), 3)
    return {
        "aggregate_score": aggregate_score,
        "rubric": rubric,
        "scenario_count": len(scenario_reports),
        "scenarios": scenario_reports,
        "pass": aggregate_score >= 0.85,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_eval(), indent=2))
