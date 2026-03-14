# Eurydice Deployment Notes

## Required environment variables

- `DB_USER`
- `DB_PASSWORD`
- `DB_PASSWORD_SECRET_NAME`
  - Recommended for Cloud Run and CI/CD
  - If set, the deploy script mounts `DB_PASSWORD` from Secret Manager instead of sending a literal env var
- `DB_NAME`
- `CLOUDSQL_INSTANCE_CONNECTION_NAME`
- `VISTA_MODEL_ID`
  - Use `gemini-live-2.5-flash-native-audio`
  - Do not use the deprecated preview model `gemini-live-2.5-flash-preview-native-audio-09-2025`
  - The deploy script exits early if the deprecated preview model is configured
- `VISTA_LOCATION`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
  - Optional when Application Default Credentials already have Firebase Admin access
  - May be either a file path or the raw JSON service account payload
- `FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME`
  - Recommended for Cloud Run when you want the Admin SDK JSON injected from Secret Manager

## Useful optional environment variables

- `VISTA_FALLBACK_LOCATION`
  - Defaults to `us-central1`
- `VISTA_FIREBASE_WEB_CONFIG`
  - Public client config used by the backend auth exchange and the frontend
  - Must include `apiKey`
  - May still be stored in Secret Manager for consistency
- `VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME`
  - If set, the deploy script mounts `VISTA_FIREBASE_WEB_CONFIG` from Secret Manager
- `VISTA_SESSION_COOKIE_NAME`
  - Defaults to `eurydice_session`
- `VISTA_SESSION_COOKIE_SECURE`
  - Set this to `true` in Cloud Run / HTTPS
- `VISTA_SESSION_COOKIE_SAMESITE`
  - Defaults to `lax`
- `VISTA_SESSION_COOKIE_MAX_AGE_SECONDS`
  - Defaults to 5 days
- `VISTA_PROJECT_ID`
  - Usually not needed if ADC already resolves the Google Cloud project id
- `VISTA_USE_ADK`
  - Defaults to `false`
  - The base backend install does not include `google-adk`
  - Leave this disabled unless you have built a separate compatible environment for the experimental ADK bridge
  - If disabled, the backend uses the direct Vertex websocket bridge only
- `CLOUD_RUN_TIMEOUT_SECONDS`
  - The deploy script clamps this to at least `600`
  - Defaults to `900`
- `CLOUD_RUN_CONCURRENCY`
  - Defaults to `8` for a conservative websocket-friendly setting
- `FRONTEND_FEATURES_URI`
  - Optional private asset source for landing-page feature art
  - Point it at a GCS folder such as `gs://eurydice-private-assets/features`
  - Cloud Build syncs that folder into `frontend/public/features` before the Docker build
  - You can update the bucket explicitly with `bash infra/sync_feature_assets.sh`
- `ALLOW_UNAUTHENTICATED`
  - Defaults to `false`
  - If set to `true`, the deploy script passes `--allow-unauthenticated`
  - This requires `run.services.setIamPolicy`, so it is usually better to leave this off in CI and manage public invoker access separately

## Cloud Run notes

- Deploy the backend as a single FastAPI service.
- Set Cloud Run request timeout to at least 10 minutes if you want long-running websocket sessions.
- Websocket clients must reconnect after timeouts or connection loss.
- Each open websocket keeps a Cloud Run instance busy, so keep concurrency conservative for the MVP.
- The deploy script only attaches Cloud SQL when `CLOUDSQL_INSTANCE_CONNECTION_NAME` is set.
- The deploy script prefers Secret Manager for `DB_PASSWORD`, `FIREBASE_SERVICE_ACCOUNT_JSON`, and `VISTA_FIREBASE_WEB_CONFIG` when the corresponding `*_SECRET_NAME` variables are set.
- The deploy script now creates or updates a Cloud Run job named `${SERVICE_NAME}-migrations` by default and runs `alembic upgrade head` before deploying the service revision.
- The service account needs:
  - Vertex AI permissions sufficient to call the Live API (`aiplatform`)
  - Cloud SQL Client
  - Firebase Admin access if you rely on ADC instead of `FIREBASE_SERVICE_ACCOUNT_JSON`
  - `roles/storage.objectViewer` on the private asset bucket if you use `FRONTEND_FEATURES_URI`
- The repository ignores `frontend/public/features/*` so those assets stay out of git and are expected to arrive via local copy or Cloud Build sync.
- To mirror the local landing-page feature art into the private bucket:
  - `FRONTEND_FEATURES_URI=gs://YOUR_BUCKET/features bash infra/sync_feature_assets.sh`
  - Add `--dry-run` to preview changes first

## Troubleshooting

### Missing required environment variable

- Local shell exports only affect your current terminal session.
- GitHub Actions reads repository variables from `.github/workflows/deploy-cloudrun.yml`, not your local shell.
- If `infra/deploy_cloudrun.sh` exits with `Missing required environment variable: ...`, set it either:
  - locally with `export VARIABLE_NAME=value`
  - or in GitHub with `gh variable set VARIABLE_NAME --body "value"`

### Firebase session cookie creation failed on the backend

- If Cloud Run logs show `invalid_grant: Invalid JWT Signature.`, the backend Firebase Admin credential is invalid at runtime.
- In this repo, the secret to rotate is `vista-firebase-adminsdk`.
- After adding a new secret version, redeploy Cloud Run so the latest secret version is mounted.
- This is an Admin SDK secret problem, not a `VISTA_FIREBASE_WEB_CONFIG` problem.

## GitHub CI/CD

- The repository includes `.github/workflows/deploy-cloudrun.yml`.
- It uses GitHub Actions plus Google Workload Identity Federation instead of a long-lived JSON key.
- Configure these GitHub repository variables before enabling automatic deploys:
  - `GCP_PROJECT_ID`
  - `GCP_REGION`
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_GITHUB_DEPLOY_SERVICE_ACCOUNT`
  - `CLOUDSQL_INSTANCE_CONNECTION_NAME`
  - `DB_USER`
  - `DB_NAME`
  - `DB_PASSWORD_SECRET_NAME`
  - `FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME`
  - `VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME` (optional if you still set it as a literal env var)
  - `FRONTEND_FEATURES_URI` (optional, for private landing-page feature art)
- Optional repository variables:
  - `CLOUD_RUN_SERVICE_NAME`
  - `CLOUD_RUN_SERVICE_ACCOUNT`
  - `CLOUD_RUN_BUILD_SERVICE_ACCOUNT`
  - `CLOUD_RUN_ALLOW_UNAUTHENTICATED`
  - `VISTA_MODEL_ID`
  - `VISTA_LOCATION`
  - `VISTA_FALLBACK_LOCATION`
  - `VISTA_PROJECT_ID`
  - `VISTA_USE_ADK`
  - `VISTA_SESSION_COOKIE_SECURE` (`true` recommended in Cloud Run)
- If `FRONTEND_FEATURES_URI` is set, grant the Cloud Build service account read access to that bucket or prefix:
  - `gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET --member="serviceAccount:YOUR_BUILD_SERVICE_ACCOUNT" --role="roles/storage.objectViewer"`
- The workflow calls the same `infra/deploy_cloudrun.sh` script, so local and CI deploys stay aligned.

## Local development

- Run Postgres locally and point the backend to it with `DB_HOST` and `DB_PORT`.
- Use a Firebase dev project and set `VISTA_FIREBASE_WEB_CONFIG` in `backend/.env`.
- If email/password fields are blank, the backend performs anonymous sign-in and issues a session cookie.
- Run `cd backend && alembic upgrade head` before starting `uvicorn app.main:app` locally.
- For real Eurydice SVG score rendering, install the optional music stack:
  - `pip install -r backend/requirements-music.txt`
  - Without that extra dependency, Eurydice render endpoints still return MusicXML fallback payloads.
