# Backend Scaffold

The backend is a small FastAPI service that defines the first stable seams for the new Ancient Greek live tutor.

## Responsibilities in this scaffold

- expose a health endpoint and runtime metadata
- bootstrap a tutor session with mode, tools, and prompt preview
- provide a placeholder `/ws/live` websocket for future Gemini Live integration
- keep agent pieces separated so ADK and tool work can grow without reshaping the app

## Key modules

```text
backend/app/
├── api/                   # HTTP route registration and dependencies
├── agents/
│   ├── orchestration/     # ADK-facing orchestration placeholder
│   ├── tools/             # parse / grade / drill tool definitions
│   ├── modes.py           # tutoring mode definitions
│   ├── prompts.py         # system prompt builder
│   └── session_state.py   # session state snapshot scaffold
├── live/                  # Gemini Live integration planning layer
├── main.py                # FastAPI app and websocket placeholder
├── schemas.py             # request / response models
└── settings.py            # env-driven configuration
```

## Endpoints

- `GET /healthz`
- `GET /api/runtime`
- `GET /api/live/modes`
- `POST /api/live/session`
- `WS /ws/live`

## Running locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## What is still a stub

- Gemini Live auth and transport
- ADK agent graph and tool execution
- storage, auth, and session persistence
- production observability

