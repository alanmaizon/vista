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

# Build and deploy using Cloud Build and Cloud Run
gcloud config set run/region "$GOOGLE_CLOUD_LOCATION"
gcloud config set project "$GOOGLE_CLOUD_PROJECT"

# Build and deploy the container from the backend directory
gcloud run deploy "$SERVICE_NAME" \
  --source=./backend \
  --allow-unauthenticated \
  --set-env-vars "CLOUDSQL_INSTANCE_CONNECTION_NAME=$CLOUDSQL_INSTANCE" \
  --set-env-vars "DB_USER=$DB_USER" \
  --set-env-vars "DB_PASSWORD=$DB_PASSWORD" \
  --set-env-vars "DB_NAME=$DB_NAME" \
  --set-env-vars "VISTA_MODEL_ID=${VISTA_MODEL_ID:-gemini-live-2.5-flash-native-audio}" \
  --set-env-vars "VISTA_LOCATION=${VISTA_LOCATION:-$GOOGLE_CLOUD_LOCATION}" \
  --set-env-vars "VISTA_SYSTEM_INSTRUCTIONS=${VISTA_SYSTEM_INSTRUCTIONS:-}" \
  --add-cloudsql-instances "$CLOUDSQL_INSTANCE" \
  --port=8080

echo "Deployment complete."