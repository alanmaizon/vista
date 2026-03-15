import base64
from types import SimpleNamespace

from fastapi.testclient import TestClient

import backend.app.main as live_main


class FakeGeminiConnection:
    def __init__(self, messages: list[SimpleNamespace]) -> None:
        self._messages = messages
        self.tool_responses: list[dict[str, object]] = []
        self.sent_texts: list[str] = []
        self.end_turn_count = 0
        self.closed = False

    async def receive(self):
        for message in self._messages:
            yield message

    async def send_text(self, text: str) -> None:  # pragma: no cover - not used in this test
        self.sent_texts.append(text)

    async def send_audio_chunk(  # pragma: no cover - not used in this test
        self,
        *,
        audio_bytes: bytes,
        mime_type: str,
        is_final_chunk: bool,
    ) -> None:
        _ = (audio_bytes, mime_type, is_final_chunk)

    async def send_image_chunk(  # pragma: no cover - not used in this test
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> None:
        _ = (image_bytes, mime_type)

    async def end_turn(self) -> None:  # pragma: no cover - not used in this test
        self.end_turn_count += 1

    async def send_tool_response(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        response: dict[str, object],
    ) -> None:
        self.tool_responses.append(
            {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "response": response,
            }
        )

    async def close(self) -> None:
        self.closed = True


def _build_fake_messages() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            setup_complete=SimpleNamespace(session_id="upstream-session-1"),
            server_content=None,
            tool_call=None,
            tool_call_cancellation=None,
            usage_metadata=None,
            go_away=None,
            session_resumption_update=None,
            voice_activity_detection_signal=None,
            voice_activity=None,
        ),
        SimpleNamespace(
            setup_complete=None,
            server_content=SimpleNamespace(
                model_turn=SimpleNamespace(
                    parts=[
                        SimpleNamespace(text="Let's parse this together.", inline_data=None),
                        SimpleNamespace(
                            text=None,
                            inline_data=SimpleNamespace(
                                data=b"\x00\x01\x02",
                                mime_type="audio/pcm;rate=24000",
                            ),
                        ),
                    ]
                ),
                turn_complete=True,
                interrupted=False,
                grounding_metadata=None,
                generation_complete=True,
                input_transcription=None,
                output_transcription=None,
                url_context_metadata=None,
                turn_complete_reason=None,
                waiting_for_input=False,
            ),
            tool_call=None,
            tool_call_cancellation=None,
            usage_metadata=None,
            go_away=None,
            session_resumption_update=None,
            voice_activity_detection_signal=None,
            voice_activity=None,
        ),
        SimpleNamespace(
            setup_complete=None,
            server_content=None,
            tool_call=SimpleNamespace(
                function_calls=[
                    SimpleNamespace(
                        id="tool-call-1",
                        name="parse_passage",
                        args={"text": "logos gar didaskalos", "focus_word": "logos"},
                    )
                ]
            ),
            tool_call_cancellation=None,
            usage_metadata=None,
            go_away=None,
            session_resumption_update=None,
            voice_activity_detection_signal=None,
            voice_activity=None,
        ),
        SimpleNamespace(
            setup_complete=None,
            server_content=None,
            tool_call=None,
            tool_call_cancellation=None,
            usage_metadata=None,
            go_away=None,
            session_resumption_update=SimpleNamespace(
                new_handle="resume-handle-1",
                resumable=True,
                last_consumed_client_message_index=7,
            ),
            voice_activity_detection_signal=None,
            voice_activity=None,
        ),
        SimpleNamespace(
            setup_complete=None,
            server_content=None,
            tool_call=None,
            tool_call_cancellation=None,
            usage_metadata=None,
            go_away=SimpleNamespace(time_left="9.5s"),
            session_resumption_update=None,
            voice_activity_detection_signal=None,
            voice_activity=None,
        ),
    ]


def test_live_bridge_maps_gemini_messages_to_contract(monkeypatch) -> None:
    fake_connection = FakeGeminiConnection(messages=_build_fake_messages())

    async def fake_connect_session(*, system_prompt: str, tools):
        assert "Current tutoring mode:" in system_prompt
        assert any(tool.name == "parse_passage" for tool in tools)
        return fake_connection

    monkeypatch.setattr(live_main.gemini_gateway, "connect_session", fake_connect_session)

    client = TestClient(live_main.app)
    with client.websocket_connect("/ws/live") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "server.ready"

        websocket.send_json(
            {
                "type": "client.hello",
                "protocol_version": "2026-03-15",
                "session_id": "session-integration-1",
                "mode": "guided_reading",
                "capabilities": {
                    "audio_input": True,
                    "audio_output": True,
                    "image_input": True,
                    "supports_barge_in": True,
                },
                "client_name": "pytest-client",
            }
        )

        # Exact event count from hello + fake Gemini stream messages above.
        events = [websocket.receive_json() for _ in range(14)]

    event_types = [event["type"] for event in events]
    assert "server.output.text" in event_types
    assert "server.output.audio" in event_types
    assert "server.tool.call" in event_types
    assert "server.tool.result" in event_types
    assert "server.session.update" in event_types

    text_event = next(event for event in events if event["type"] == "server.output.text")
    assert text_event["text"] == "Let's parse this together."
    assert text_event["is_final"] is True

    audio_event = next(event for event in events if event["type"] == "server.output.audio")
    assert audio_event["mime_type"] == "audio/pcm;rate=24000"
    assert audio_event["data_base64"] == base64.b64encode(b"\x00\x01\x02").decode("ascii")
    assert audio_event["is_final_chunk"] is True

    tool_result = next(event for event in events if event["type"] == "server.tool.result")
    assert tool_result["status"] == "completed"
    assert tool_result["tool_name"] == "parse_passage"
    assert tool_result["result"]["tool"] == "parse_passage"
    assert tool_result["result"]["status"] == "ok"

    go_away_update = next(
        event
        for event in events
        if event["type"] == "server.session.update" and event.get("go_away") is True
    )
    assert go_away_update["time_left_ms"] == 9500

    assert fake_connection.tool_responses
    assert fake_connection.tool_responses[0]["tool_name"] == "parse_passage"
    assert fake_connection.closed is True


def test_live_turn_end_runs_orchestration_preflight(monkeypatch) -> None:
    fake_connection = FakeGeminiConnection(messages=[])

    async def fake_connect_session(*, system_prompt: str, tools):
        assert "Current tutoring mode:" in system_prompt
        assert any(tool.name == "parse_passage" for tool in tools)
        return fake_connection

    monkeypatch.setattr(live_main.gemini_gateway, "connect_session", fake_connect_session)

    client = TestClient(live_main.app)
    with client.websocket_connect("/ws/live") as websocket:
        websocket.receive_json()  # server.ready
        websocket.send_json(
            {
                "type": "client.hello",
                "protocol_version": "2026-03-15",
                "session_id": "session-orch-1",
                "mode": "morphology_coach",
                "target_text": "logos gar didaskalos",
                "capabilities": {
                    "audio_input": True,
                    "audio_output": True,
                    "image_input": True,
                    "supports_barge_in": True,
                },
                "client_name": "pytest-client",
            }
        )
        websocket.receive_json()  # ready status
        websocket.receive_json()  # listening status

        websocket.send_json(
            {
                "type": "client.input.text",
                "protocol_version": "2026-03-15",
                "turn_id": "turn-orch-1",
                "text": "please parse logos",
                "source": "typed",
                "is_final": True,
            }
        )
        websocket.receive_json()  # learner transcript echo

        websocket.send_json(
            {
                "type": "client.turn.end",
                "protocol_version": "2026-03-15",
                "turn_id": "turn-orch-1",
                "reason": "done",
            }
        )

        orchestration_events = [websocket.receive_json() for _ in range(5)]

    event_types = [event["type"] for event in orchestration_events]
    assert "server.tool.call" in event_types
    assert "server.tool.result" in event_types
    assert event_types.count("server.status") >= 2

    tool_result = next(event for event in orchestration_events if event["type"] == "server.tool.result")
    assert tool_result["status"] == "completed"
    assert tool_result["tool_name"] == "parse_passage"
    assert tool_result["result"]["orchestration_stage"] == "tool_preflight"
    assert tool_result["result"]["orchestration_engine"] in {"google-adk", "heuristic-fallback"}

    assert fake_connection.end_turn_count == 1
    assert fake_connection.sent_texts
    assert any(
        sent_text.startswith("[orchestration_context]") for sent_text in fake_connection.sent_texts
    )


def test_live_text_is_forwarded_once_per_closed_turn(monkeypatch) -> None:
    fake_connection = FakeGeminiConnection(messages=[])

    async def fake_connect_session(*, system_prompt: str, tools):
        assert "Current tutoring mode:" in system_prompt
        assert any(tool.name == "parse_passage" for tool in tools)
        return fake_connection

    monkeypatch.setattr(live_main.gemini_gateway, "connect_session", fake_connect_session)

    client = TestClient(live_main.app)
    with client.websocket_connect("/ws/live") as websocket:
        websocket.receive_json()  # server.ready
        websocket.send_json(
            {
                "type": "client.hello",
                "protocol_version": "2026-03-15",
                "session_id": "session-memory-1",
                "mode": "guided_reading",
                "capabilities": {
                    "audio_input": True,
                    "audio_output": True,
                    "image_input": True,
                    "supports_barge_in": True,
                },
                "client_name": "pytest-client",
            }
        )
        websocket.receive_json()  # ready status
        websocket.receive_json()  # listening status

        websocket.send_json(
            {
                "type": "client.input.text",
                "protocol_version": "2026-03-15",
                "turn_id": "turn-memory-1",
                "text": "what is logos?",
                "source": "typed",
                "is_final": True,
            }
        )
        websocket.receive_json()  # learner transcript echo
        websocket.send_json(
            {
                "type": "client.turn.end",
                "protocol_version": "2026-03-15",
                "turn_id": "turn-memory-1",
                "reason": "done",
            }
        )
        _ = [websocket.receive_json() for _ in range(3)]  # closed, orchestration status, thinking status

        websocket.send_json(
            {
                "type": "client.input.text",
                "protocol_version": "2026-03-15",
                "turn_id": "turn-memory-2",
                "text": "what context?",
                "source": "typed",
                "is_final": True,
            }
        )
        websocket.receive_json()  # learner transcript echo
        websocket.send_json(
            {
                "type": "client.turn.end",
                "protocol_version": "2026-03-15",
                "turn_id": "turn-memory-2",
                "reason": "done",
            }
        )
        _ = [websocket.receive_json() for _ in range(3)]  # closed, orchestration status, thinking status

    assert len(fake_connection.sent_texts) == 2
    assert fake_connection.sent_texts[0] == "what is logos?"
    assert "[session_context]" in fake_connection.sent_texts[1]
    assert "Learner: what is logos?" in fake_connection.sent_texts[1]
    assert "Current learner turn: what context?" in fake_connection.sent_texts[1]
    assert fake_connection.end_turn_count == 2
