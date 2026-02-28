#!/bin/bash
# Deploy the Vista AI backend to Cloud Run.

set -euo pipefail

# Ensure required environment variables are set
if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  echo "GOOGLE_CLOUD_PROJECT must be set" >&2
  exit 1
fi
if [[ -z "${GOOGLE_CLOUD_LOCATION:-}" ]]; then
  echo "GOOGLE_CLOUD_LOCATION must be set" >&2
  exit 1
fi

# Optional Cloud SQL instance connection name
CLOUDSQL_INSTANCE=${CLOUDSQL_INSTANCE_CONNECTION_NAME:-}
DB_USER=${DB_USER:-vista_user}
DB_PASSWORD=${DB_PASSWORD:-changeme}
DB_NAME=${DB_NAME:-vista_ai}

SERVICE_NAME=${SERVICE_NAME:-vista-ai-backend}
VISTA_MODEL_ID=${VISTA_MODEL_ID:-gemini-live-2.5-flash-native-audio}
VISTA_LOCATION=${VISTA_LOCATION:-$GOOGLE_CLOUD_LOCATION}
VISTA_FALLBACK_LOCATION=${VISTA_FALLBACK_LOCATION:-us-central1}
VISTA_PROJECT_ID=${VISTA_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}
VISTA_USE_ADK=${VISTA_USE_ADK:-true}
CLOUD_RUN_TIMEOUT_SECONDS=${CLOUD_RUN_TIMEOUT_SECONDS:-900}
CLOUD_RUN_CONCURRENCY=${CLOUD_RUN_CONCURRENCY:-8}

if [[ "$VISTA_MODEL_ID" == "gemini-live-2.5-flash-preview-native-audio-09-2025" ]]; then
  echo "VISTA_MODEL_ID uses the deprecated preview live model and cannot be deployed." >&2
  exit 1
fi

if (( CLOUD_RUN_TIMEOUT_SECONDS < 600 )); then
  CLOUD_RUN_TIMEOUT_SECONDS=600
fi

# Build and deploy using Cloud Build and Cloud Run
gcloud config set run/region "$GOOGLE_CLOUD_LOCATION"
gcloud config set project "$GOOGLE_CLOUD_PROJECT"

# Build and deploy the container from the backend directory
DEPLOY_ARGS=(
  "$SERVICE_NAME"
  --source=./backend
  --allow-unauthenticated
  --timeout="${CLOUD_RUN_TIMEOUT_SECONDS}s"
  --concurrency="$CLOUD_RUN_CONCURRENCY"
  --set-env-vars "DB_USER=$DB_USER"
  --set-env-vars "DB_PASSWORD=$DB_PASSWORD"
  --set-env-vars "DB_NAME=$DB_NAME"
  --set-env-vars "VISTA_MODEL_ID=$VISTA_MODEL_ID"
  --set-env-vars "VISTA_LOCATION=$VISTA_LOCATION"
  --set-env-vars "VISTA_FALLBACK_LOCATION=$VISTA_FALLBACK_LOCATION"
  --set-env-vars "VISTA_PROJECT_ID=$VISTA_PROJECT_ID"
  --set-env-vars "VISTA_USE_ADK=$VISTA_USE_ADK"
  --set-env-vars "VISTA_SYSTEM_INSTRUCTIONS=${VISTA_SYSTEM_INSTRUCTIONS:-}"
  --port=8080
)

if [[ -n "$CLOUDSQL_INSTANCE" ]]; then
  DEPLOY_ARGS+=(
    --set-env-vars "CLOUDSQL_INSTANCE_CONNECTION_NAME=$CLOUDSQL_INSTANCE"
    --add-cloudsql-instances "$CLOUDSQL_INSTANCE"
  )
fi

gcloud run deploy "${DEPLOY_ARGS[@]}"

echo "Deployment complete."
