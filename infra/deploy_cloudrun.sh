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
ALLOW_UNAUTHENTICATED=${ALLOW_UNAUTHENTICATED:-false}
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

join_by_comma() {
  local IFS=","
  echo "$*"
}

join_by_delimiter() {
  local delimiter="$1"
  shift
  local joined=""
  local item
  for item in "$@"; do
    if [[ -z "$joined" ]]; then
      joined="$item"
    else
      joined="${joined}${delimiter}${item}"
    fi
  done
  printf '%s' "$joined"
}

SERVICE_EXISTS=0
if gcloud run services describe "$SERVICE_NAME" >/dev/null 2>&1; then
  SERVICE_EXISTS=1
fi

# Build and deploy the container from the backend directory
ENV_UPDATES=(
  "DB_USER=$DB_USER"
  "DB_NAME=$DB_NAME"
  "VISTA_MODEL_ID=$VISTA_MODEL_ID"
  "VISTA_LOCATION=$VISTA_LOCATION"
  "VISTA_FALLBACK_LOCATION=$VISTA_FALLBACK_LOCATION"
  "VISTA_PROJECT_ID=$VISTA_PROJECT_ID"
  "VISTA_USE_ADK=$VISTA_USE_ADK"
  "VISTA_MUSIC_SYSTEM_INSTRUCTIONS=$VISTA_MUSIC_SYSTEM_INSTRUCTIONS"
  "VISTA_SYSTEM_INSTRUCTIONS=${VISTA_SYSTEM_INSTRUCTIONS:-}"
)
SECRET_UPDATES=()
REMOVE_SECRETS=()

DEPLOY_ARGS=(
  "$SERVICE_NAME"
  --source=./backend
  --timeout="${CLOUD_RUN_TIMEOUT_SECONDS}s"
  --concurrency="$CLOUD_RUN_CONCURRENCY"
  --service-account "$CLOUD_RUN_SERVICE_ACCOUNT"
  --build-service-account "projects/${GOOGLE_CLOUD_PROJECT}/serviceAccounts/${CLOUD_RUN_BUILD_SERVICE_ACCOUNT}"
  --port=8080
)

if [[ "$ALLOW_UNAUTHENTICATED" == "true" ]]; then
  DEPLOY_ARGS+=(--allow-unauthenticated)
fi

if [[ -n "$CLOUDSQL_INSTANCE" ]]; then
  ENV_UPDATES+=("CLOUDSQL_INSTANCE_CONNECTION_NAME=$CLOUDSQL_INSTANCE")
  DEPLOY_ARGS+=(--add-cloudsql-instances "$CLOUDSQL_INSTANCE")
else
  ENV_UPDATES+=("DB_HOST=$DB_HOST")
  if [[ -n "$DB_PORT" ]]; then
    ENV_UPDATES+=("DB_PORT=$DB_PORT")
  fi
fi

if [[ -n "$DB_PASSWORD_SECRET_NAME" ]]; then
  SECRET_UPDATES+=("DB_PASSWORD=${DB_PASSWORD_SECRET_NAME}:${DB_PASSWORD_SECRET_VERSION}")
else
  REMOVE_SECRETS+=("DB_PASSWORD")
  ENV_UPDATES+=("DB_PASSWORD=$DB_PASSWORD")
fi

if [[ -n "$FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME" ]]; then
  SECRET_UPDATES+=("FIREBASE_SERVICE_ACCOUNT_JSON=${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME}:${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_VERSION}")
elif [[ -n "$FIREBASE_SERVICE_ACCOUNT_JSON" ]]; then
  REMOVE_SECRETS+=("FIREBASE_SERVICE_ACCOUNT_JSON")
  ENV_UPDATES+=("FIREBASE_SERVICE_ACCOUNT_JSON=$FIREBASE_SERVICE_ACCOUNT_JSON")
fi

if [[ -n "$VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME" ]]; then
  SECRET_UPDATES+=("VISTA_FIREBASE_WEB_CONFIG=${VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME}:${VISTA_FIREBASE_WEB_CONFIG_SECRET_VERSION}")
elif [[ -n "$VISTA_FIREBASE_WEB_CONFIG" ]]; then
  REMOVE_SECRETS+=("VISTA_FIREBASE_WEB_CONFIG")
  ENV_UPDATES+=("VISTA_FIREBASE_WEB_CONFIG=$VISTA_FIREBASE_WEB_CONFIG")
fi

if (( ${#REMOVE_SECRETS[@]} > 0 )); then
  DEPLOY_ARGS+=(
    --remove-secrets "$(join_by_comma "${REMOVE_SECRETS[@]}")"
  )
fi

ENV_REMOVALS_FOR_SECRET_MIGRATION=()
MIGRATION_SECRET_UPDATES=()
if [[ -n "$DB_PASSWORD_SECRET_NAME" ]]; then
  ENV_REMOVALS_FOR_SECRET_MIGRATION+=("DB_PASSWORD")
  MIGRATION_SECRET_UPDATES+=("DB_PASSWORD=${DB_PASSWORD_SECRET_NAME}:${DB_PASSWORD_SECRET_VERSION}")
fi
if [[ -n "$FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME" ]]; then
  ENV_REMOVALS_FOR_SECRET_MIGRATION+=("FIREBASE_SERVICE_ACCOUNT_JSON")
  MIGRATION_SECRET_UPDATES+=("FIREBASE_SERVICE_ACCOUNT_JSON=${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME}:${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_VERSION}")
fi
if [[ -n "$VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME" ]]; then
  ENV_REMOVALS_FOR_SECRET_MIGRATION+=("VISTA_FIREBASE_WEB_CONFIG")
  MIGRATION_SECRET_UPDATES+=("VISTA_FIREBASE_WEB_CONFIG=${VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME}:${VISTA_FIREBASE_WEB_CONFIG_SECRET_VERSION}")
fi

if (( SERVICE_EXISTS == 1 && ${#ENV_REMOVALS_FOR_SECRET_MIGRATION[@]} > 0 && ${#MIGRATION_SECRET_UPDATES[@]} > 0 )); then
  gcloud run services update "$SERVICE_NAME" \
    --region="$GOOGLE_CLOUD_LOCATION" \
    --remove-env-vars "$(join_by_comma "${ENV_REMOVALS_FOR_SECRET_MIGRATION[@]}")" \
    --update-secrets "$(join_by_comma "${MIGRATION_SECRET_UPDATES[@]}")" \
    >/dev/null
fi

if (( ${#SECRET_UPDATES[@]} > 0 )); then
  DEPLOY_ARGS+=(
    --update-secrets "$(join_by_comma "${SECRET_UPDATES[@]}")"
  )
fi

if (( ${#ENV_UPDATES[@]} > 0 )); then
  # Use a custom delimiter because some values (for example JSON) contain commas.
  ENV_DELIMITER="~"
  DEPLOY_ARGS+=(
    --update-env-vars "^${ENV_DELIMITER}^$(join_by_delimiter "${ENV_DELIMITER}" "${ENV_UPDATES[@]}")"
  )
fi

gcloud run deploy "${DEPLOY_ARGS[@]}"

echo "Cloud Run service account: ${CLOUD_RUN_SERVICE_ACCOUNT}"
echo "Cloud Build service account: ${CLOUD_RUN_BUILD_SERVICE_ACCOUNT}"
echo "Deployment complete."
