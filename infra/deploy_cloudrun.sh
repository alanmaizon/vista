#!/usr/bin/env bash
set -euo pipefail

GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-${GCP_REGION:-us-central1}}"
SERVICE_NAME="${SERVICE_NAME:-eurydice-live}"
IMAGE_REPO="${IMAGE_REPO:-cloud-run-source-deploy}"
IMAGE_NAME="${IMAGE_NAME:-$SERVICE_NAME}"
IMAGE_URI="${IMAGE_URI:-${GOOGLE_CLOUD_LOCATION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${IMAGE_REPO}/${IMAGE_NAME}}"
CLOUD_RUN_SERVICE_ACCOUNT="${CLOUD_RUN_SERVICE_ACCOUNT:-}"
CLOUD_RUN_BUILD_SERVICE_ACCOUNT="${CLOUD_RUN_BUILD_SERVICE_ACCOUNT:-}"
VISTA_MODEL_ID="${VISTA_MODEL_ID:-gemini-live-2.5-flash-native-audio}"
VISTA_LOCATION="${VISTA_LOCATION:-$GOOGLE_CLOUD_LOCATION}"
VISTA_FALLBACK_LOCATION="${VISTA_FALLBACK_LOCATION:-$VISTA_LOCATION}"
VISTA_PROJECT_ID="${VISTA_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}"
VISTA_USE_ADK="${VISTA_USE_ADK:-false}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_var GOOGLE_CLOUD_PROJECT

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
  --substitutions "_IMAGE=${IMAGE_URI},_FEATURES_URI="
)

if [[ -n "$CLOUD_RUN_BUILD_SERVICE_ACCOUNT" ]]; then
  build_cmd+=(--service-account "$(as_service_account_resource "$CLOUD_RUN_BUILD_SERVICE_ACCOUNT")")
fi

"${build_cmd[@]}"

deploy_cmd=(
  gcloud run deploy "$SERVICE_NAME"
  --project "$GOOGLE_CLOUD_PROJECT"
  --region "$GOOGLE_CLOUD_LOCATION"
  --image "$IMAGE_URI"
  --concurrency 8
  --timeout 900
  --max-instances 3
  --update-env-vars "VISTA_MODEL_ID=${VISTA_MODEL_ID},VISTA_LOCATION=${VISTA_LOCATION},VISTA_FALLBACK_LOCATION=${VISTA_FALLBACK_LOCATION},VISTA_PROJECT_ID=${VISTA_PROJECT_ID},VISTA_USE_ADK=${VISTA_USE_ADK}"
)

if [[ -n "$CLOUD_RUN_SERVICE_ACCOUNT" ]]; then
  deploy_cmd+=(--service-account "$CLOUD_RUN_SERVICE_ACCOUNT")
fi

if [[ "$ALLOW_UNAUTHENTICATED" == "true" ]]; then
  deploy_cmd+=(--allow-unauthenticated)
fi

"${deploy_cmd[@]}"
