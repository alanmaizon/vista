# Vista AI MVP Deployment Notes

## Required environment variables

- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `CLOUDSQL_INSTANCE_CONNECTION_NAME`
- `VISTA_MODEL_ID`
  - Use `gemini-live-2.5-flash-native-audio`
  - Do not use the deprecated preview model `gemini-live-2.5-flash-preview-native-audio-09-2025`
- `VISTA_LOCATION`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
  - Optional when Application Default Credentials already have Firebase Admin access
  - May be either a file path or the raw JSON service account payload

## Useful optional environment variables

- `VISTA_FALLBACK_LOCATION`
  - Defaults to `us-central1`
- `VISTA_PROJECT_ID`
  - Usually not needed if ADC already resolves the Google Cloud project id

## Cloud Run notes

- Deploy the backend as a single FastAPI service.
- Set Cloud Run request timeout to at least 10 minutes if you want long-running websocket sessions.
- Websocket clients must reconnect after timeouts or connection loss.
- Each open websocket keeps a Cloud Run instance busy, so keep concurrency conservative for the MVP.
- The service account needs:
  - Vertex AI permissions sufficient to call the Live API (`aiplatform`)
  - Cloud SQL Client
  - Firebase Admin access if you rely on ADC instead of `FIREBASE_SERVICE_ACCOUNT_JSON`

## Local development

- Run Postgres locally and point the backend to it with `DB_HOST` and `DB_PORT`.
- Use a Firebase dev project and paste the Firebase web config JSON into the browser client.
- If email/password fields are blank, the browser client attempts anonymous sign-in.
