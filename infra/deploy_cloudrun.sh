#!/bin/bash
# Deploy the Vista AI backend to Cloud Run.

set -euo pipefail

if [[ -n "${DEPLOY_ENV_FILE:-}" ]]; then
  if [[ ! -f "${DEPLOY_ENV_FILE}" ]]; then
    echo "DEPLOY_ENV_FILE does not exist: ${DEPLOY_ENV_FILE}" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "${DEPLOY_ENV_FILE}"
  set +a
fi

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
DB_PASSWORD_SECRET_NAME=${DB_PASSWORD_SECRET_NAME:-}
DB_PASSWORD_SECRET_VERSION=${DB_PASSWORD_SECRET_VERSION:-latest}
DB_NAME=${DB_NAME:-vista_ai}
DB_HOST=${DB_HOST:-}
DB_PORT=${DB_PORT:-}
FIREBASE_SERVICE_ACCOUNT_JSON=${FIREBASE_SERVICE_ACCOUNT_JSON:-}
FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME=${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME:-}
FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_VERSION=${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_VERSION:-latest}

SERVICE_NAME=${SERVICE_NAME:-vista-ai-backend}
VISTA_MODEL_ID=${VISTA_MODEL_ID:-gemini-live-2.5-flash-native-audio}
VISTA_LOCATION=${VISTA_LOCATION:-$GOOGLE_CLOUD_LOCATION}
VISTA_FALLBACK_LOCATION=${VISTA_FALLBACK_LOCATION:-us-central1}
VISTA_PROJECT_ID=${VISTA_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}
VISTA_USE_ADK=${VISTA_USE_ADK:-false}
VISTA_FIREBASE_WEB_CONFIG=${VISTA_FIREBASE_WEB_CONFIG:-}
VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME=${VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME:-}
VISTA_FIREBASE_WEB_CONFIG_SECRET_VERSION=${VISTA_FIREBASE_WEB_CONFIG_SECRET_VERSION:-latest}
VISTA_MUSIC_SYSTEM_INSTRUCTIONS=${VISTA_MUSIC_SYSTEM_INSTRUCTIONS:-}
CLOUD_RUN_TIMEOUT_SECONDS=${CLOUD_RUN_TIMEOUT_SECONDS:-900}
CLOUD_RUN_CONCURRENCY=${CLOUD_RUN_CONCURRENCY:-8}

if [[ "$VISTA_MODEL_ID" == "gemini-live-2.5-flash-preview-native-audio-09-2025" ]]; then
  echo "VISTA_MODEL_ID uses the deprecated preview live model and cannot be deployed." >&2
  exit 1
fi

if (( CLOUD_RUN_TIMEOUT_SECONDS < 600 )); then
  CLOUD_RUN_TIMEOUT_SECONDS=600
fi

if [[ -z "$DB_PASSWORD_SECRET_NAME" && "$DB_PASSWORD" == "changeme" ]]; then
  echo "DB_PASSWORD is still the unsafe default value 'changeme'. Refusing to deploy." >&2
  echo "Export the real DB_PASSWORD first, or set DB_PASSWORD_SECRET_NAME / DEPLOY_ENV_FILE to production values." >&2
  exit 1
fi

if [[ -z "$CLOUDSQL_INSTANCE" && -z "$DB_HOST" ]]; then
  echo "CLOUDSQL_INSTANCE_CONNECTION_NAME or DB_HOST must be set for deployment." >&2
  echo "Cloud Run cannot use the backend default of 127.0.0.1 unless you intentionally run a database inside the container." >&2
  exit 1
fi

# Build and deploy using Cloud Build and Cloud Run
gcloud config set run/region "$GOOGLE_CLOUD_LOCATION"
gcloud config set project "$GOOGLE_CLOUD_PROJECT"

PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"
CLOUD_RUN_SERVICE_ACCOUNT=${CLOUD_RUN_SERVICE_ACCOUNT:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}
CLOUD_RUN_BUILD_SERVICE_ACCOUNT=${CLOUD_RUN_BUILD_SERVICE_ACCOUNT:-$CLOUD_RUN_SERVICE_ACCOUNT}

# Build and deploy the container from the backend directory
DEPLOY_ARGS=(
  "$SERVICE_NAME"
  --source=./backend
  --allow-unauthenticated
  --timeout="${CLOUD_RUN_TIMEOUT_SECONDS}s"
  --concurrency="$CLOUD_RUN_CONCURRENCY"
  --set-env-vars "DB_USER=$DB_USER"
  --set-env-vars "DB_NAME=$DB_NAME"
  --set-env-vars "VISTA_MODEL_ID=$VISTA_MODEL_ID"
  --set-env-vars "VISTA_LOCATION=$VISTA_LOCATION"
  --set-env-vars "VISTA_FALLBACK_LOCATION=$VISTA_FALLBACK_LOCATION"
  --set-env-vars "VISTA_PROJECT_ID=$VISTA_PROJECT_ID"
  --set-env-vars "VISTA_USE_ADK=$VISTA_USE_ADK"
  --set-env-vars "VISTA_MUSIC_SYSTEM_INSTRUCTIONS=$VISTA_MUSIC_SYSTEM_INSTRUCTIONS"
  --set-env-vars "VISTA_SYSTEM_INSTRUCTIONS=${VISTA_SYSTEM_INSTRUCTIONS:-}"
  --service-account "$CLOUD_RUN_SERVICE_ACCOUNT"
  --build-service-account "projects/${GOOGLE_CLOUD_PROJECT}/serviceAccounts/${CLOUD_RUN_BUILD_SERVICE_ACCOUNT}"
  --port=8080
)

if [[ -n "$CLOUDSQL_INSTANCE" ]]; then
  DEPLOY_ARGS+=(
    --set-env-vars "CLOUDSQL_INSTANCE_CONNECTION_NAME=$CLOUDSQL_INSTANCE"
    --add-cloudsql-instances "$CLOUDSQL_INSTANCE"
  )
else
  DEPLOY_ARGS+=(
    --set-env-vars "DB_HOST=$DB_HOST"
  )
  if [[ -n "$DB_PORT" ]]; then
    DEPLOY_ARGS+=(
      --set-env-vars "DB_PORT=$DB_PORT"
    )
  fi
fi

if [[ -n "$DB_PASSWORD_SECRET_NAME" ]]; then
  DEPLOY_ARGS+=(
    --remove-env-vars "DB_PASSWORD"
    --update-secrets "DB_PASSWORD=${DB_PASSWORD_SECRET_NAME}:${DB_PASSWORD_SECRET_VERSION}"
  )
else
  DEPLOY_ARGS+=(
    --remove-secrets "DB_PASSWORD"
    --set-env-vars "DB_PASSWORD=$DB_PASSWORD"
  )
fi

if [[ -n "$FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME" ]]; then
  DEPLOY_ARGS+=(
    --remove-env-vars "FIREBASE_SERVICE_ACCOUNT_JSON"
    --update-secrets "FIREBASE_SERVICE_ACCOUNT_JSON=${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME}:${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_VERSION}"
  )
elif [[ -n "$FIREBASE_SERVICE_ACCOUNT_JSON" ]]; then
  DEPLOY_ARGS+=(
    --remove-secrets "FIREBASE_SERVICE_ACCOUNT_JSON"
    --set-env-vars "^~^FIREBASE_SERVICE_ACCOUNT_JSON=$FIREBASE_SERVICE_ACCOUNT_JSON"
  )
fi

if [[ -n "$VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME" ]]; then
  DEPLOY_ARGS+=(
    --remove-env-vars "VISTA_FIREBASE_WEB_CONFIG"
    --update-secrets "VISTA_FIREBASE_WEB_CONFIG=${VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME}:${VISTA_FIREBASE_WEB_CONFIG_SECRET_VERSION}"
  )
elif [[ -n "$VISTA_FIREBASE_WEB_CONFIG" ]]; then
  DEPLOY_ARGS+=(
    --remove-secrets "VISTA_FIREBASE_WEB_CONFIG"
  )
  # Use a custom delimiter because the JSON value contains commas.
  DEPLOY_ARGS+=(
    --set-env-vars "^~^VISTA_FIREBASE_WEB_CONFIG=$VISTA_FIREBASE_WEB_CONFIG"
  )
fi

gcloud run deploy "${DEPLOY_ARGS[@]}"

echo "Cloud Run service account: ${CLOUD_RUN_SERVICE_ACCOUNT}"
echo "Cloud Build service account: ${CLOUD_RUN_BUILD_SERVICE_ACCOUNT}"
echo "Deployment complete."
