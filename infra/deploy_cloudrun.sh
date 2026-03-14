#!/usr/bin/env bash
set -euo pipefail

GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-${GCP_REGION:-us-central1}}"
SERVICE_NAME="${SERVICE_NAME:-vista-ai-backend}"
MIGRATION_JOB_NAME="${MIGRATION_JOB_NAME:-${SERVICE_NAME}-migrations}"
IMAGE_REPO="${IMAGE_REPO:-cloud-run-source-deploy}"
IMAGE_NAME="${IMAGE_NAME:-$SERVICE_NAME}"
IMAGE_URI="${IMAGE_URI:-${GOOGLE_CLOUD_LOCATION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${IMAGE_REPO}/${IMAGE_NAME}}"
CLOUD_RUN_SERVICE_ACCOUNT="${CLOUD_RUN_SERVICE_ACCOUNT:-}"
CLOUD_RUN_BUILD_SERVICE_ACCOUNT="${CLOUD_RUN_BUILD_SERVICE_ACCOUNT:-}"
FRONTEND_FEATURES_URI="${FRONTEND_FEATURES_URI:-}"
CLOUDSQL_INSTANCE_CONNECTION_NAME="${CLOUDSQL_INSTANCE_CONNECTION_NAME:-}"
DB_USER="${DB_USER:-}"
DB_NAME="${DB_NAME:-}"
DB_PASSWORD_SECRET_NAME="${DB_PASSWORD_SECRET_NAME:-}"
FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME="${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME:-}"
VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME="${VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME:-}"
VISTA_MODEL_ID="${VISTA_MODEL_ID:-gemini-live-2.5-flash-native-audio}"
VISTA_LOCATION="${VISTA_LOCATION:-$GOOGLE_CLOUD_LOCATION}"
VISTA_FALLBACK_LOCATION="${VISTA_FALLBACK_LOCATION:-$VISTA_LOCATION}"
VISTA_PROJECT_ID="${VISTA_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}"
VISTA_USE_ADK="${VISTA_USE_ADK:-false}"
VISTA_SESSION_COOKIE_SECURE="${VISTA_SESSION_COOKIE_SECURE:-false}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-false}"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_var GOOGLE_CLOUD_PROJECT
require_var DB_USER
require_var DB_NAME
require_var DB_PASSWORD_SECRET_NAME
require_var FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME
require_var VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME
require_var CLOUDSQL_INSTANCE_CONNECTION_NAME

as_service_account_resource() {
  local value="$1"
  if [[ "$value" == projects/*/serviceAccounts/* ]]; then
    printf '%s\n' "$value"
    return
  fi
  printf 'projects/%s/serviceAccounts/%s\n' "$GOOGLE_CLOUD_PROJECT" "$value"
}

gcloud config set run/region "$GOOGLE_CLOUD_LOCATION" >/dev/null
gcloud config set project "$GOOGLE_CLOUD_PROJECT" >/dev/null

build_cmd=(
  gcloud builds submit .
  --project "$GOOGLE_CLOUD_PROJECT"
  --config infra/cloudbuild.yaml
  --substitutions "_IMAGE=${IMAGE_URI},_FEATURES_URI=${FRONTEND_FEATURES_URI}"
)

if [[ -n "$CLOUD_RUN_BUILD_SERVICE_ACCOUNT" ]]; then
  build_cmd+=(--service-account "$(as_service_account_resource "$CLOUD_RUN_BUILD_SERVICE_ACCOUNT")")
fi

"${build_cmd[@]}"

migration_cmd=(
  gcloud run jobs create "$MIGRATION_JOB_NAME"
  --project "$GOOGLE_CLOUD_PROJECT"
  --region "$GOOGLE_CLOUD_LOCATION"
  --image "$IMAGE_URI"
  --command alembic
  --args=-c,alembic.ini,upgrade,head
  --tasks 1
  --max-retries 0
  --set-cloudsql-instances "$CLOUDSQL_INSTANCE_CONNECTION_NAME"
  --set-env-vars "DB_USER=${DB_USER},DB_NAME=${DB_NAME},CLOUDSQL_INSTANCE_CONNECTION_NAME=${CLOUDSQL_INSTANCE_CONNECTION_NAME}"
  --set-secrets "DB_PASSWORD=${DB_PASSWORD_SECRET_NAME}:latest"
)

if [[ -n "$CLOUD_RUN_SERVICE_ACCOUNT" ]]; then
  migration_cmd+=(--service-account "$CLOUD_RUN_SERVICE_ACCOUNT")
fi

if gcloud run jobs describe "$MIGRATION_JOB_NAME" \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_LOCATION" >/dev/null 2>&1; then
  migration_cmd[3]="update"
fi

"${migration_cmd[@]}"

gcloud run jobs execute "$MIGRATION_JOB_NAME" \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_LOCATION" \
  --wait

deploy_cmd=(
  gcloud run deploy "$SERVICE_NAME"
  --project "$GOOGLE_CLOUD_PROJECT"
  --region "$GOOGLE_CLOUD_LOCATION"
  --image "$IMAGE_URI"
  --concurrency 8
  --timeout 900
  --max-instances 3
  --set-cloudsql-instances "$CLOUDSQL_INSTANCE_CONNECTION_NAME"
  --update-env-vars "DB_USER=${DB_USER},DB_NAME=${DB_NAME},VISTA_MODEL_ID=${VISTA_MODEL_ID},VISTA_LOCATION=${VISTA_LOCATION},VISTA_FALLBACK_LOCATION=${VISTA_FALLBACK_LOCATION},VISTA_PROJECT_ID=${VISTA_PROJECT_ID},VISTA_USE_ADK=${VISTA_USE_ADK},VISTA_SESSION_COOKIE_SECURE=${VISTA_SESSION_COOKIE_SECURE},CLOUDSQL_INSTANCE_CONNECTION_NAME=${CLOUDSQL_INSTANCE_CONNECTION_NAME}"
  --update-secrets "DB_PASSWORD=${DB_PASSWORD_SECRET_NAME}:latest,FIREBASE_SERVICE_ACCOUNT_JSON=${FIREBASE_SERVICE_ACCOUNT_JSON_SECRET_NAME}:latest,VISTA_FIREBASE_WEB_CONFIG=${VISTA_FIREBASE_WEB_CONFIG_SECRET_NAME}:latest"
)

if [[ -n "$CLOUD_RUN_SERVICE_ACCOUNT" ]]; then
  deploy_cmd+=(--service-account "$CLOUD_RUN_SERVICE_ACCOUNT")
fi

if [[ "$ALLOW_UNAUTHENTICATED" == "true" ]]; then
  deploy_cmd+=(--allow-unauthenticated)
fi

"${deploy_cmd[@]}"
