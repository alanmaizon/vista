from backend.app.live.protocol import (
    CLIENT_EVENT_TYPES,
    INPUT_AUDIO_MIME_TYPE,
    LIVE_PROTOCOL_VERSION,
    OUTPUT_AUDIO_MIME_TYPE,
    SERVER_EVENT_TYPES,
    build_server_ready_event,
    parse_client_event,
    parse_server_event,
    protocol_contract_summary,
)


def test_protocol_summary_lists_expected_shapes() -> None:
    summary = protocol_contract_summary()
    assert summary["protocol_version"] == LIVE_PROTOCOL_VERSION
    assert summary["accepted_client_events"] == CLIENT_EVENT_TYPES
    assert summary["emitted_server_events"] == SERVER_EVENT_TYPES
    assert summary["input_audio_mime_type"] == INPUT_AUDIO_MIME_TYPE
    assert summary["output_audio_mime_type"] == OUTPUT_AUDIO_MIME_TYPE


def test_parse_client_audio_event() -> None:
    event = parse_client_event(
        {
            "type": "client.input.audio",
            "turn_id": "turn-1",
            "chunk_index": 0,
            "mime_type": INPUT_AUDIO_MIME_TYPE,
            "data_base64": "AQID",
        }
    )
    assert event.type == "client.input.audio"
    assert event.chunk_index == 0


def test_parse_client_hello_event() -> None:
    event = parse_client_event(
        {
            "type": "client.hello",
            "session_id": "session-123",
            "mode": "guided_reading",
            "capabilities": {
                "audio_input": True,
                "audio_output": True,
                "image_input": True,
                "supports_barge_in": True,
            },
        }
    )
    assert event.type == "client.hello"
    assert event.session_id == "session-123"


def test_parse_server_ready_event() -> None:
    event = parse_server_event(
        build_server_ready_event(connection_id="conn-123", websocket_path="/ws/live").model_dump(
            mode="json"
        )
    )
    assert event.type == "server.ready"
    assert event.protocol_version == LIVE_PROTOCOL_VERSION
