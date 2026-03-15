# Eurydice Live Backend Contract

This is the current backend contract for the reset `Eurydice Live` service.

Use this document as the source of truth for any new frontend. Legacy music APIs, database-backed lesson flows, and old auth/session routes are still present in the repo history, but they are not the active backend surface.

## Purpose

The current backend supports one thing:

- a real-time Gemini Live music tutor that can hear speech
- receive camera frames
- stream assistant audio/text/transcripts back
- keep lightweight in-memory diagnostics for demos and debugging

## Active Endpoints

### `GET /`

Returns a tiny service descriptor.

Example response:

```json
{
  "service": "eurydice-live",
  "status": "ok",
  "ws_path": "/ws/live",
  "docs_path": "/docs"
}
```

### `GET /health`

Simple health check.

Example response:

```json
{
  "status": "ok"
}
```

### `GET /api/client-config`

Returns browser-safe Firebase config if `VISTA_FIREBASE_WEB_CONFIG` is set. This is optional and may return `null`.

Example response:

```json
{
  "firebaseConfig": null
}
```

### `GET /api/runtime`

Returns the current backend runtime shape that a frontend can use to self-check environment and supported message types.

Example response:

```json
{
  "service": "eurydice-live",
  "model_id": "gemini-live-2.5-flash-native-audio",
  "location": "us-central1",
  "fallback_location": "us-central1",
  "project_id": "your-gcp-project",
  "use_adk": false,
  "adk_available": false,
  "adk_detail": "test",
  "active_session_count": 0,
  "accepted_client_messages": [
    "client.init",
    "client.audio",
    "client.audio_end",
    "client.video",
    "client.text",
    "client.stop"
  ],
  "emitted_server_messages": [
    "server.status",
    "server.audio",
    "server.transcript",
    "server.text",
    "server.summary",
    "error"
  ]
}
```

### `GET /api/runtime/debug`

Returns in-memory diagnostics for active and recent live sessions. Use this for demo proof, debugging, and backend sanity checks.

Each session snapshot also includes a `pingpong` report for spoken turns. That report is keyed off `client.audio_end` and shows:

- aggregate averages such as `average_first_response_ms`, `average_first_audio_ms`, and `average_full_turn_ms`
- completed vs pending turn counts
- `recent_turns[]` entries with:
  - `user_turn_ended_at`
  - `user_transcript_final`
  - `first_response_ms`
  - `first_transcript_ms`
  - `first_audio_ms`
  - `full_turn_ms`
  - `status`

Example response:

```json
{
  "service": "eurydice-live",
  "model_id": "gemini-live-2.5-flash-native-audio",
  "location": "us-central1",
  "fallback_location": "us-central1",
  "project_id": "your-gcp-project",
  "use_adk": false,
  "adk_available": false,
  "adk_detail": "test",
  "active_session_count": 1,
  "active_sessions": [
    {
      "session_id": "2d4...",
      "mode": "music_tutor",
      "instrument": "voice",
      "piece": "Caro mio ben",
      "goal": "shape the opening phrase",
      "camera_expected": true,
      "transport": "direct",
      "opened_at": "2026-03-14T15:10:00.000000+00:00",
      "last_activity_at": "2026-03-14T15:10:04.000000+00:00",
      "closed_at": null,
      "inbound": {
        "client.init": 1,
        "client.audio": 3,
        "client.video": 2,
        "client.audio_end": 1
      },
      "outbound": {
        "server.status": 1,
        "server.transcript": 2,
        "server.audio": 4
      }
    }
  ],
  "recent_sessions": []
}
```

### `POST /api/live/session-profile`

Normalizes and validates live session metadata before opening the websocket.

Request body:

```json
{
  "mode": "music_tutor",
  "instrument": "voice",
  "piece": "Caro mio ben",
  "goal": "shape the opening phrase",
  "camera_expected": true
}
```

Rules:

- `mode` must normalize to one of:
  - `music_tutor`
  - `sight_reading`
  - `technique_practice`
  - `ear_training`
- `instrument` is optional, max 80 chars
- `piece` is optional, max 120 chars
- `goal` is optional, max 240 chars
- repeated whitespace is collapsed

Response body:

```json
{
  "session_profile": {
    "mode": "music_tutor",
    "instrument": "voice",
    "piece": "Caro mio ben",
    "goal": "shape the opening phrase",
    "camera_expected": true
  },
  "opening_hint": "Start the session with a brief spoken greeting. Acknowledge this context: instrument=voice, piece=Caro mio ben, goal=shape the opening phrase, camera_expected=true. Then ask one short next-step question.",
  "label": "voice · Caro mio ben · shape the opening phrase"
}
```

## WebSocket

### URL

`WS /ws/live`

### Connection Flow

1. Open websocket
2. First message must be `client.init`
3. Backend validates init payload and connects to Gemini Live
4. Backend sends `server.status`
5. Backend seeds Gemini with an opening prompt
6. Frontend streams audio, video, and text messages
7. Backend forwards Gemini events back to the client
8. Frontend sends `client.stop` to end cleanly
9. Backend returns `server.summary`

## Client Messages

### `client.init`

Must be the first websocket message.

Example:

```json
{
  "type": "client.init",
  "mode": "music_tutor",
  "instrument": "voice",
  "piece": "Caro mio ben",
  "goal": "shape the opening phrase",
  "camera_expected": true
}
```

Notes:

- The backend strips the `type` field and validates the rest as a `LiveSessionProfile`
- If invalid, the backend sends an `error` event and closes the session path

### `client.audio`

PCM audio chunk from the browser mic.

Example:

```json
{
  "type": "client.audio",
  "mime": "audio/pcm;rate=16000",
  "data_b64": "BASE64_PCM_BYTES"
}
```

### `client.audio_end`

Tells the backend the current spoken turn has paused and should be flushed upstream.

Example:

```json
{
  "type": "client.audio_end"
}
```

### `client.video`

JPEG frame from the camera.

Example:

```json
{
  "type": "client.video",
  "mime": "image/jpeg",
  "data_b64": "BASE64_JPEG_BYTES"
}
```

### `client.text`

Optional typed user text.

Example:

```json
{
  "type": "client.text",
  "text": "Let's work on the opening phrase."
}
```

### `client.stop`

Ends the session.

Example:

```json
{
  "type": "client.stop"
}
```

## Server Messages

### `server.status`

Sent once after a successful Gemini connection.

Example:

```json
{
  "type": "server.status",
  "state": "connected",
  "mode": "music_tutor",
  "skill": "MUSIC_LIVE_TUTOR",
  "transport": "direct",
  "model_id": "gemini-live-2.5-flash-native-audio",
  "location": "us-central1",
  "session_id": "2d4...",
  "instrument": "voice",
  "piece": "Caro mio ben",
  "goal": "shape the opening phrase",
  "camera_expected": true
}
```

### `server.audio`

Assistant audio chunk.

Common fields:

- `type`
- `data_b64`
- `mime`
- may include `turn_id`, `chunk_index`, `turn_complete`

### `server.transcript`

Partial or final transcript from user or assistant audio.

Common fields:

- `type`
- `role`
- `text`
- `partial`
- may include `turn_id`, `chunk_index`, `turn_complete`

### `server.text`

Assistant text output.

Common fields:

- `type`
- `text`
- may include `turn_id`, `chunk_index`, `turn_complete`

### `server.summary`

Sent after `client.stop`.

Example:

```json
{
  "type": "server.summary",
  "scenario": "live_music_tutor",
  "session_id": "2d4...",
  "bullets": [
    "Realtime voice tutoring is enabled.",
    "Camera frames can be streamed during the session.",
    "Gemini transport: direct Vertex Live.",
    "Instrument: voice.",
    "Piece: Caro mio ben.",
    "Goal: shape the opening phrase."
  ]
}
```

### `error`

Returned when the client sends malformed JSON, bad base64, unsupported types, or an invalid init payload.

Example:

```json
{
  "type": "error",
  "message": "Invalid base64 payload"
}
```

## Recommended Frontend Flow

1. Call `POST /api/live/session-profile`
2. Show the normalized profile label and opening hint in the UI
3. Open `/ws/live`
4. Send `client.init` with the normalized session profile
5. Wait for `server.status`
6. Start streaming:
   - `client.audio`
   - `client.audio_end`
   - `client.video`
   - `client.text` when needed
7. Render:
   - `server.audio`
   - `server.transcript`
   - `server.text`
8. On stop, send `client.stop`
9. Optionally poll `GET /api/runtime/debug` during demos

## Non-Goals For This Backend

These are intentionally not part of the active serving path right now:

- database-backed sessions
- Firebase auth enforcement
- score import / render / compare endpoints
- lesson orchestration state machine
- persistent analytics storage
- tool-call based music workflows

## Best Next Additions

If you extend this backend, keep it small:

1. Add a lightweight client auth token only if the demo truly needs it
2. Add one score snapshot endpoint if the frontend needs uploaded image capture outside websocket frames
3. Add structured logs around websocket lifecycle for Cloud Run troubleshooting
4. Keep new state in memory unless persistence is essential to the demo
