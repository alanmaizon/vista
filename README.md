# Ancient Greek Live Tutor

This repository is a fresh scaffold for a voice-first multimodal Ancient Greek tutor built around Gemini Live API, Google ADK, and Google Cloud. It is intentionally minimal: the goal is to provide a clean foundation for live tutoring work without carrying over the old Eurydice product logic.

## Why this scaffold looks this way

The prior codebase already proved out a sensible split:

- `frontend/` for a browser-based live session UI
- `backend/` for FastAPI APIs, live session orchestration, and Google integrations

This scaffold keeps that shape, while leaving the archival application under `legacy/` untouched.

## Repository layout

```text
vista/
├── backend/          # FastAPI scaffold for session bootstrap, runtime info, and Gemini Live websocket bridge
├── docs/             # Product and architecture notes
├── frontend/         # Vite + React + TypeScript scaffold for the tutor session UI
├── infra/            # Deployment notes for future Google Cloud work
├── legacy/           # Archived Eurydice codebase
└── scripts/          # Small helper scripts for local development
```

## Current status

What exists now:

- A minimal live session UI prepared for microphone, camera, and worksheet image intake
- A FastAPI backend with runtime metadata, session bootstrap, and a Gemini Live-backed `/ws/live` bridge with scaffold fallback
- Skeletal agent layers for prompts, session state, tutoring modes, tool registry, Gemini Live planning, and ADK orchestration
- Deterministic starter tools for parsing, grading, and drill generation, wired into live tool calls
- Focused documentation explaining the intended architecture and next implementation steps

What is intentionally not implemented yet:

- Actual Google ADK orchestration logic
- Persistent storage, auth, or deployment automation

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Or use the helper scripts from the repo root:

```bash
./scripts/dev-backend.sh
./scripts/dev-frontend.sh
```

## Next steps

1. Wire the ADK orchestration layer to real tutoring modes and tool execution.
2. Improve deterministic tools with richer morphology coverage and structured rubric outputs.
3. Add persistence for session state, learner progress, and uploaded worksheet metadata.
4. Decide on the first Google Cloud deployment slice, likely backend to Cloud Run and frontend to static hosting or a lightweight edge deploy.

For a more detailed breakdown, see `docs/product.md` and `docs/architecture.md`.
For the websocket message contract used by the current live bridge, see `docs/live-event-contract.md`.
