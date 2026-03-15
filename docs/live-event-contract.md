# Live Event Contract

This document defines the repository-level websocket contract for `/ws/live`.

It is not a copy of Google’s raw Live API wire format. Instead, it is the contract between this browser client and our FastAPI backend, which acts as the Gemini Live and ADK broker.

## Why this layer exists

- the browser needs a stable, app-specific protocol even if upstream Gemini Live details evolve
- the backend must mediate tool calls, session resumption, and tutor state
- the frontend should receive normalized transcript, tool, and status events no matter how the backend talks to Gemini

## Design assumptions

- websocket frames are JSON envelopes
- audio and image payloads are Base64-encoded inside JSON for now
- learner input is grouped by `turn_id`
- the browser calls `POST /api/live/session` first, then opens `/ws/live`
- the backend uses one upstream Gemini Live response modality per session, but may still emit transcript events to the browser alongside audio

## Handshake flow

1. Browser opens `WS /ws/live`
2. Server sends `server.ready`
3. Browser sends `client.hello` with the `session_id` received from `POST /api/live/session`
4. Browser streams `client.input.*` events for the current learner turn
5. Browser closes the turn with `client.turn.end`
6. Server emits tutor status, transcript, tool, output, and turn lifecycle events

## Client -> server events

### `client.hello`

Sent once after the socket opens.

```json
{
  "type": "client.hello",
  "protocol_version": "2026-03-15",
  "session_id": "session-abc123",
  "mode": "guided_reading",
  "target_text": "logos gar egeneto",
  "preferred_response_language": "English",
  "capabilities": {
    "audio_input": true,
    "audio_output": true,
    "image_input": true,
    "supports_barge_in": true
  },
  "client_name": "frontend"
}
```

### `client.input.text`

Use for typed turns, OCR text, or transcript correction.

### `client.input.audio`

Use for microphone chunks.

Requirements:

- MIME type: `audio/pcm;rate=16000`
- payload field: `data_base64`
- include `turn_id` and monotonically increasing `chunk_index`

### `client.input.image`

Use for a camera frame or uploaded worksheet image.

Supported MIME types:

- `image/jpeg`
- `image/png`
- `image/webp`

### `client.turn.end`

Closes the current learner turn and tells the backend to start model-orchestration work for that turn.

### `client.control.interrupt`

Signals user barge-in or an explicit stop action.

### `client.control.ping`

Optional keepalive.

## Server -> client events

### `server.ready`

Sent immediately after the websocket opens. This advertises protocol version, expected MIME types, and event families.

### `server.status`

Short lifecycle updates. Current phases:

- `ready`
- `listening`
- `receiving_input`
- `thinking`
- `tool_running`
- `speaking`
- `interrupted`
- `closing`
- `closed`
- `error`

### `server.transcript`

Normalized transcript rows for both learner and tutor output. This is the main feed for transcript UI rendering.

### `server.output.text`

Direct text generation chunks for text-mode sessions or debugging.

### `server.output.audio`

Tutor audio chunks for playback.

Requirements:

- MIME type: `audio/pcm;rate=24000`
- payload field: `data_base64`
- include `turn_id` and `chunk_index`

### `server.tool.call`

Backend-visible tool request event, useful for debugging and future UI introspection.

### `server.tool.result`

Tool completion or failure event.

### `server.turn`

Lifecycle markers such as learner turn closure, model turn completion, or interruption.

### `server.session.update`

Reserved for Gemini Live resumption handles, go-away notices, and compression/resumption state.

### `server.error`

Structured websocket-level errors.

## Event priorities

Frontend code should treat events this way:

1. `server.error` is highest priority and should surface immediately.
2. `server.output.audio` drives playback.
3. `server.transcript` drives transcript UI.
4. `server.tool.*` is secondary and mostly for observability.
5. `server.status` and `server.turn` drive session state transitions.

## Known future changes

- We may move audio payloads from Base64 JSON to binary websocket frames if transport overhead becomes material.
- `server.session.update` will grow when Gemini Live session resumption is wired in.
- `server.tool.result` will likely gain dedicated typed payloads for parse, grade, and drill outputs.

## Primary references

- Gemini Live API capabilities guide: https://ai.google.dev/gemini-api/docs/live-guide
- Gemini Live session management guide: https://ai.google.dev/gemini-api/docs/live-session
- Gemini Live tool use guide: https://ai.google.dev/gemini-api/docs/live-tools
- Google ADK custom WebSocket streaming guide: https://google.github.io/adk-docs/streaming/custom-streaming-ws/
