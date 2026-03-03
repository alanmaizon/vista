# Eurydice

<p align="center">
  <img src="logo.svg" alt="Eurydice logo" width="120" height="120">
</p>

Eurydice is a real-time multimodal music tutor built for the Gemini Live Agent Challenge. It can hear a student play, read their score via the camera, coach them bar by bar in voice, and adapt the lesson live until the phrase is learned.

This repository is organised into two main parts:

* `backend/` — A FastAPI service that exposes REST endpoints for session management, music score import/rendering, guided lesson workflows, user authentication via Firebase, and a WebSocket endpoint that proxies audio/video to the Gemini Live API. The service is designed to run on Google Cloud Run and connect to a Cloud SQL (PostgreSQL) database.
* `frontend/` — A placeholder for a React application. For hackathon purposes the `backend/app/static/` directory includes a browser client that can be used directly.

## Setup overview

Use Python `3.11`, `3.12`, or `3.13` for local development. Python `3.14` is not supported yet by the pinned dependency stack.

1. **Enable required services**: Ensure the following Google Cloud services are enabled in your project: `aiplatform`, `run`, `cloudsql`, `secretmanager`, and `iam`.
2. **Create a Cloud SQL database**: Provision a Postgres instance and create a database for sessions. Update the environment variables in the Cloud Run deployment script accordingly.
3. **Configure Firebase**: Add Firebase to your project, enable authentication, and provide a service account JSON for server-side token verification. The backend expects a Firebase ID token for each HTTP/WebSocket request.
4. **Deploy the backend**: Use the provided Dockerfile and `deploy_cloudrun.sh` script in the `infra/` directory to build and deploy the FastAPI service. The script sets environment variables needed by the application.
5. **Install music extras** (optional): For SVG score rendering install `pip install -r backend/requirements-music.txt`. For advanced audio analysis (CREPE pitch verification) install `pip install -r backend/requirements-music-ml.txt`.

For more details about the product specification, refer to `docs/EURYDICE_CHALLENGE_BRIEF.md`. For deployment instructions, see `docs/DEPLOYMENT.md`.
