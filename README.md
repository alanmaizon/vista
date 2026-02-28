# Vista AI Project

Vista AI is a proof‑of‑concept assistive application designed to help blind and low‑vision users navigate real‑world tasks using Google’s Gemini Live API.  The application consists of a Python backend powered by FastAPI and a React front‑end.  It supports multiple **skills**—such as finding doors, verifying products, reading text, locating objects, and assisting with simple form input—while enforcing strict safety protocols and one‑step guidance loops.

This repository is organised into two main parts:

* `backend/` — Contains a single FastAPI service that exposes REST endpoints for session management, user authentication via Firebase, and a WebSocket endpoint that proxies audio/video to the Gemini Live API.  The service is designed to run on Google Cloud Run and connect to a Cloud SQL (PostgreSQL) database.
* `frontend/` — A placeholder for a React application.  For hackathon purposes this folder includes a minimal structure; you can bootstrap a full React app (e.g., with Create React App) and point it to the WebSocket and REST endpoints exposed by the backend.

## Setup overview

1. **Enable required services**: Ensure the following Google Cloud services are enabled in your project: `aiplatform`, `run`, `cloudsql`, `secretmanager`, and `iam`.
2. **Create a Cloud SQL database**: Provision a Postgres instance and create a database for sessions.  Update the environment variables in the Cloud Run deployment script accordingly.
3. **Configure Firebase**: Add Firebase to your project, enable authentication, and provide a service account JSON for server‑side token verification.  The backend expects a Firebase ID token for each HTTP/WebSocket request.
4. **Deploy the backend**: Use the provided Dockerfile and `deploy_cloudrun.sh` script in the `infra/` directory to build and deploy the FastAPI service.  The script sets environment variables needed by the application.
5. **Develop the frontend**: Point the React app’s WebSocket client to the `/ws/live` endpoint and implement UI flows for each skill (e.g., capturing audio/video, handling confirmations, and displaying summaries).

For more details about the design principles and safety rules enforced by this application, refer to `docs/CONSTITUTION.md`.