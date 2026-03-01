# Local Setup

This is the shortest path to a working local Vista AI environment.

## Python version

- Use Python `3.11`, `3.12`, or `3.13`.
- Do not use Python `3.14` for this repo yet.
- The safest choice is Python `3.11`, which matches the backend Docker image.

## 1. Fill the backend env file

- Start from `backend/.env`.
- Replace the placeholder values with your local Postgres settings and your real Google project id.
- Keep `VISTA_MODEL_ID=gemini-live-2.5-flash-native-audio`.
- Do not use the deprecated preview model `gemini-live-2.5-flash-preview-native-audio-09-2025`.

## 2. Link Firebase

- Create or select a Firebase project, then add a Web app.
- Copy the Firebase Web config JSON.
- Fastest path: set `VISTA_FIREBASE_WEB_CONFIG` in `backend/.env` to that JSON as a single-quoted string so the UI auto-loads it.
- Fallback path: paste the same JSON into the `Firebase Config JSON` field in the browser client.
- In Firebase Authentication, enable `Anonymous` sign-in. If you want email/password login, enable `Email/Password` too.
- In Firebase Console, open `Project settings` > `Service accounts` and generate a JSON key for Firebase Admin SDK.
- Put that JSON file somewhere outside the repo if possible, then set `FIREBASE_SERVICE_ACCOUNT_JSON` in `backend/.env` to that file path.
- If you prefer ADC instead of an explicit Firebase key, leave `FIREBASE_SERVICE_ACCOUNT_JSON` blank and make sure your ADC identity can verify Firebase ID tokens.

## 3. Link Postgres or Cloud SQL

- Fastest local path: run a local Postgres instance and point `DB_HOST=127.0.0.1`, `DB_PORT=5432`.
- If you want to test against Cloud SQL from your laptop, create a Cloud SQL for PostgreSQL instance, a database, and a database user.
- For local Cloud SQL access, run the Cloud SQL Auth Proxy on TCP, then point `DB_HOST` and `DB_PORT` to the proxy.
- Leave `CLOUDSQL_INSTANCE_CONNECTION_NAME` blank during local TCP testing. This app switches to Unix sockets when that variable is set.
- In Cloud Run, set `CLOUDSQL_INSTANCE_CONNECTION_NAME` and let the deploy script attach the instance.

## 4. Link Vertex AI

- Use a Google Cloud project with billing enabled and the Vertex AI API enabled.
- Set `VISTA_PROJECT_ID` in `backend/.env` to that project id.
- For local auth, the recommended path is ADC:
  - Run `gcloud auth application-default login`
- If you use a service account key instead, set `GOOGLE_APPLICATION_CREDENTIALS` in `backend/.env` to the JSON file path.
- Make sure the identity you use has Vertex AI permissions sufficient for the Live API.

## 5. Validate and run

- Load the env file:
  - `set -a`
  - `source backend/.env`
  - `set +a`
- Validate it:
  - `python3 backend/check_local_env.py`
- Install dependencies:
  - Create a clean virtualenv with a supported Python:
    - `python3.11 -m venv .venv`
    - `source .venv/bin/activate`
  - `pip install -r backend/requirements.txt`
  - `pip install -r backend/requirements-dev.txt`
- Start the backend:
  - `cd backend`
  - `uvicorn app.main:app --reload`
- Open `http://127.0.0.1:8000`

## Official references

- Firebase Web setup: https://firebase.google.com/docs/web/setup
- Firebase Admin setup: https://firebase.google.com/docs/admin/setup
- Firebase anonymous auth: https://firebase.google.com/docs/auth/web/anonymous-auth
- Firebase email/password auth: https://firebase.google.com/docs/auth/web/password-auth
- Cloud SQL Auth Proxy quickstart: https://cloud.google.com/sql/docs/postgres/connect-instance-auth-proxy
- Cloud SQL Auth Proxy overview: https://cloud.google.com/sql/docs/postgres/connect-auth-proxy
- ADC for local development: https://cloud.google.com/docs/authentication/set-up-adc-local-dev-environment
- Vertex AI Live API: https://cloud.google.com/vertex-ai/generative-ai/docs/live-api/streamed-conversations
