# Live Tutor Architecture

This document describes the current production-oriented architecture for the Gemini Live music tutor.

## Core Principle

Eurydice is live-first: the primary experience is a guided real-time tutoring session. Deterministic music tools support the tutor and must ground musical claims.

## Conversation Pipeline

1. Frontend explicitly creates a session via `POST /api/sessions`.
2. Frontend opens `/ws/live` and sends `client.init`.
3. Backend validates auth + session ownership.
4. Backend builds runtime + centralized prompt (`PromptComposer`).
5. Backend connects `GeminiLiveBridge` (ADK preferred, direct Live API fallback).
6. Messages are exchanged as normalized events internally and flattened on the wire.

## Wire Event Contract

- Internal shape: `{type, payload, metadata}`.
- Wire shape: flat fields (for compatibility), e.g.:
  - `{"type":"server.text","text":"..."}`
  - `{"type":"server.tool_result","name":"lesson_action","ok":true,"call_id":"...","result":{...}}`
  - `{"type":"error","message":"..."}`

The backend now flattens event envelopes before sending websocket payloads.

## Prompt Architecture

`backend/app/prompts.py` is the canonical prompt builder.

- Includes stable system scaffold, tutor policy, skill policy, and tool policy.
- Includes runtime skill instructions (`runtime.skill_instructions()`).
- Appends retrieved context/memory as supporting evidence only.
- Opening prompt is skill-aware and session-aware.

## Deterministic Tooling

Registered live tools:

- `lesson_action`
- `lesson_step`
- `render_score`
- `transcribe`

Tool registration is idempotent on startup.

Tool execution is validated via Pydantic schemas, and tool cache keys are user-scoped.

## Conversation State Validation

`ConversationManager` now:

- validates non-empty turns/tool names,
- tracks pending/completed tool call IDs,
- dedupes repeated tool calls,
- rejects duplicate tool results for the same call ID.

This reduces duplicate tool execution during stream retries or reconnect jitter.

## Streaming Behavior

- Live transcripts (`server.transcript`) are incremental.
- Final assistant text (`server.text`) closes streaming turns.
- Frontend normalizes both envelope and flat message forms for robustness.

## Session Lifecycle

- Session is closed by default in the workspace.
- User must explicitly start and stop the live tutor.
- Stop path sends `client.stop`, emits summary, closes transport, persists completion.

## Evaluation Harness

`backend/app/eval_live_tutor.py` provides scenario-based architectural evals with rubric grades:

- factual correctness
- pedagogical usefulness
- tool-call correctness
- streaming behavior
- latency responsiveness
- continuity across turns

Scenarios include:

- explaining a scale,
- beginner exercise guidance,
- played phrase reaction,
- corrective feedback,
- follow-up continuity,
- clean stop/start recovery.
