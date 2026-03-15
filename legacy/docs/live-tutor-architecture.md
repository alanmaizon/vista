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

## Lesson Orchestrator

`backend/app/domains/music/lesson_orchestrator.py` sits above the Live stream and deterministic tools.

### Intent/Event Router

`backend/app/domains/music/lesson_intents.py` now classifies user and session signals into typed events before phase transitions.

- Why this replaced keyword routing:
  - single-keyword matching was brittle for ambiguous follow-ups (`again`, `was that right?`, `what now?`),
  - phrasing variation caused inconsistent phase jumps.
- Current hybrid routing stack:
  - deterministic rules first for clear intents (stop/feedback/phrase/confusion/next-step),
  - phase-aware heuristics for short ambiguous turns,
  - lightweight fallback classifier for low-signal turns.
- Typed output contract:
  - `intent`, `confidence`, `source`, `current_phase`, `recommended_transition`, `entities`.
- Deterministic authority remains unchanged:
  - musical correctness still comes from deterministic tools (`transcribe`, `lesson_action`, `lesson_step`, `render_score`), not LLM guesswork.

- Maintains explicit lesson phases:
  - `idle`
  - `intro`
  - `goal_capture`
  - `exercise_selection`
  - `listening`
  - `analysis`
  - `feedback`
  - `next_step`
  - `session_complete`
- Accepts orchestration inputs:
  - user text,
  - assistant text,
  - deterministic tool results,
  - session stop events.
- Emits orchestration outputs:
  - `server.lesson_state` (phase/status/suggested actions),
  - `server.lesson_action` (phase-aware suggested action, optional auto trigger),
  - `server.feedback_card` (compact deterministic feedback card),
  - bounded `LESSON_CONTEXT` model notes for Gemini Live.

This keeps the product flow conversation-first while preserving deterministic musical truth.

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
- Lesson-phase updates stream in-band as semantic events (`server.lesson_state`), so UI flow follows pedagogy state rather than tool-panel state.

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

- beginner asks for help with a scale,
- user plays a phrase and asks whether it was correct,
- tutor explains a concept then adapts after user struggle,
- tutor proposes a next exercise based on prior deterministic result,
- clean stop/start recovery.

## Replay Regression Validation

`backend/app/domains/music/lesson_replay.py` replays sanitized trace events against the orchestrator:

- accepted replay inputs:
  - transcript chunks (partial/final),
  - final user/assistant messages,
  - music phrase events,
  - deterministic tool results,
  - session start/stop events.
- regression checks:
  - stable phase traces,
  - no duplicate transitions,
  - no duplicate feedback cards,
  - stable behavior across stop/start and ambiguous follow-ups.

Use replay traces when changing prompts, intent routing, or phase logic to verify behavior stays stable before merge.
