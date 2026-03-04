# Eurydice

<p align="center">
  <img src="logo.svg" alt="Eurydice logo" width="120" height="120">
</p>

**A real-time multimodal music tutor built for the Gemini Live Agent Challenge.**

Eurydice can hear a student play, read their score via the camera, coach them bar by bar in voice, and adapt the lesson live until the phrase is learned.

## Quick Start

### For Users
1. Navigate to the deployed Eurydice application
2. Sign in with Firebase (anonymous or email/password)
3. Select a music skill (GUIDED_LESSON, HEAR_PHRASE, etc.)
4. Enable microphone for audio feedback
5. Optional: Enable camera for score reading
6. Start your music practice session!

### For Developers
See the [Local Setup Guide](docs/LOCAL_SETUP.md) for detailed instructions on running Eurydice locally.

## Features

🎵 **Seven Music Skills:**
- **GUIDED_LESSON** - Bar-by-bar practice with real-time feedback
- **HEAR_PHRASE** - Identify melodies, intervals, chords, and arpeggios
- **SHEET_FRAME_COACH** - Help framing sheet music for clear reading
- **READ_SCORE** - Read visible musical notation
- **COMPARE_PERFORMANCE** - Compare played vs. intended performance
- **EAR_TRAIN** - Listening drills and ear training exercises
- **GENERATE_EXAMPLE** - Original musical examples and exercises

🎤 **Real-time Audio Analysis:**
- Monophonic pitch detection using FastYIN
- Optional CREPE verification for higher accuracy
- Silence detection and note segmentation
- Interval and chord analysis

📷 **Computer Vision:**
- Camera-based score reading
- Sheet music framing assistance
- Real-time visual feedback

🔄 **Live AI Interaction:**
- WebSocket connection to Gemini Live API
- Dual-mode audio/video streaming
- Adaptive lesson pacing based on student performance

## Repository Structure

This repository is organised into two main parts:

* `backend/` — A FastAPI service that exposes REST endpoints for session management, music score import/rendering, guided lesson workflows, user authentication via Firebase, and a WebSocket endpoint that proxies audio/video to the Gemini Live API. The service is designed to run on Google Cloud Run and connect to a Cloud SQL (PostgreSQL) database.
* `frontend/` — A placeholder for a React application. For hackathon purposes the `backend/app/static/` directory includes a browser client that can be used directly.

### Key Directories
```
vista/
├── backend/
│   ├── app/
│   │   ├── domains/        # Domain-driven design modules
│   │   │   └── music/      # Music domain (transcription, comparison, rendering)
│   │   ├── live/           # Gemini Live API bridge
│   │   ├── static/         # Frontend browser client
│   │   ├── main.py         # FastAPI application entry point
│   │   ├── settings.py     # Environment configuration
│   │   └── db.py           # Database setup
│   ├── tests/              # Comprehensive test suite
│   ├── requirements.txt    # Base Python dependencies
│   └── Dockerfile          # Production container image
├── docs/                   # Documentation
│   ├── AUDIT_REPORT.md     # Codebase audit and recommendations
│   ├── EURYDICE_CHALLENGE_BRIEF.md  # Product specification
│   ├── LOCAL_SETUP.md      # Development setup guide
│   ├── DEPLOYMENT.md       # Cloud Run deployment instructions
│   └── CONSTITUTION.md     # AI system instructions
└── infra/                  # Infrastructure and deployment scripts
    └── deploy_cloudrun.sh  # Cloud Run deployment automation
```

## Architecture Overview

Eurydice follows a **client ↔ server ↔ AI** architecture:

1. **Browser client** (`backend/app/static/`) — A vanilla-JS single-page app that captures audio/video via WebRTC and communicates with the backend over REST and WebSocket.
2. **FastAPI backend** (`backend/app/`) — Handles authentication (Firebase), session management (PostgreSQL via SQLAlchemy), music score processing (Verovio), and proxies real-time audio/video to the Gemini Live API over a WebSocket bridge.
3. **Gemini Live API** — Provides multimodal AI responses (voice coaching, score reading, ear training) streamed back to the client in real time.

Data flows in a loop: the client streams media frames to the backend, which forwards them to Gemini; Gemini's responses are relayed back through the WebSocket to the browser, where the UI updates captions, score overlays, and lesson state accordingly.

## Setup overview

Use Python `3.11`, `3.12`, or `3.13` for local development. Python `3.14` is not supported yet by the pinned dependency stack.

1. **Enable required services**: Ensure the following Google Cloud services are enabled in your project: `aiplatform`, `run`, `cloudsql`, `secretmanager`, and `iam`.
2. **Create a Cloud SQL database**: Provision a Postgres instance and create a database for sessions. Update the environment variables in the Cloud Run deployment script accordingly.
3. **Configure Firebase**: Add Firebase to your project, enable authentication, and provide a service account JSON for server-side token verification. The backend expects a Firebase ID token for each HTTP/WebSocket request.
4. **Deploy the backend**: Use the provided Dockerfile and `deploy_cloudrun.sh` script in the `infra/` directory to build and deploy the FastAPI service. The script sets environment variables needed by the application.
5. **Install music extras** (optional): For SVG score rendering install `pip install -r backend/requirements-music.txt`. For advanced audio analysis (CREPE pitch verification) install `pip install -r backend/requirements-music-ml.txt`.

For more details about the product specification, refer to `docs/EURYDICE_CHALLENGE_BRIEF.md`. For deployment instructions, see `docs/DEPLOYMENT.md`.

## Technology Stack

### Backend
- **FastAPI** - Modern async web framework
- **SQLAlchemy** - Async ORM with PostgreSQL
- **Firebase Admin SDK** - Authentication
- **Vertex AI** - Gemini Live API integration
- **Verovio** (optional) - Music notation rendering
- **CREPE** (optional) - ML-based pitch detection

### Frontend
- **Vanilla JavaScript** (ES6 modules)
- **Firebase Web SDK** - Client-side authentication
- **WebRTC** - Audio/video capture
- **WebSocket** - Real-time communication

### Infrastructure
- **Google Cloud Run** - Serverless container hosting
- **Cloud SQL (PostgreSQL)** - Managed database
- **Secret Manager** - Credential storage
- **Docker** - Containerization

## Development

### Code Quality Tools
- **ESLint** - JavaScript linting (`.eslintrc.json`)
- **Prettier** - Code formatting (`.prettierrc.json`)
- **Black** - Python formatting
- **Flake8** - Python linting
- **pre-commit** - Git hooks for automated checks

### Running Tests
```bash
# Backend tests
cd backend
pytest

# Run specific test file
pytest tests/test_music_transcription.py

# With coverage
pytest --cov=app --cov-report=html
```

### Code Style
```bash
# Format Python code
black backend/app

# Lint Python code
flake8 backend/app --max-line-length=120

# Format JavaScript
prettier --write "backend/app/static/*.js"

# Lint JavaScript
eslint backend/app/static/*.js
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## Documentation

- **[Product Specification](docs/EURYDICE_CHALLENGE_BRIEF.md)** - Comprehensive challenge brief
- **[Local Setup](docs/LOCAL_SETUP.md)** - Step-by-step development guide
- **[Deployment](docs/DEPLOYMENT.md)** - Cloud Run deployment instructions
- **[Constitution](docs/CONSTITUTION.md)** - AI system behavior rules
- **[Audit Report](docs/AUDIT_REPORT.md)** - Codebase audit and improvements

## Security & Privacy

- All user authentication via Firebase ID tokens
- Session ownership validation on all endpoints
- Input sanitization for user-provided data
- Environment variables for sensitive configuration
- No credentials stored in source code

## License

This project is built for the Gemini Live Agent Challenge.

## Contributing

This is a hackathon project with a deadline of **March 16, 2026**. For code quality standards and improvement suggestions, see `docs/AUDIT_REPORT.md`.
