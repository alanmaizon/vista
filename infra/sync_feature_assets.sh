#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${SOURCE_DIR:-frontend/public/features}"
DESTINATION_URI="${FRONTEND_FEATURES_URI:-${1:-}}"
DRY_RUN="${DRY_RUN:-false}"

usage() {
  cat <<'EOF'
Usage:
  FRONTEND_FEATURES_URI=gs://YOUR_BUCKET/features bash infra/sync_feature_assets.sh
  bash infra/sync_feature_assets.sh gs://YOUR_BUCKET/features
  bash infra/sync_feature_assets.sh --dry-run gs://YOUR_BUCKET/features

Environment variables:
  FRONTEND_FEATURES_URI  Optional destination bucket prefix.
  SOURCE_DIR             Optional local source directory. Defaults to frontend/public/features.
  DRY_RUN                Set to true to preview changes without uploading.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="true"
  DESTINATION_URI="${FRONTEND_FEATURES_URI:-${2:-}}"
fi

if [[ -z "${DESTINATION_URI}" ]]; then
  echo "Missing destination URI. Set FRONTEND_FEATURES_URI or pass gs://.../features as the first argument." >&2
  usage >&2
  exit 1
fi

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "Source directory does not exist: ${SOURCE_DIR}" >&2
  exit 1
fi

DESTINATION_URI="${DESTINATION_URI%/}"

mapfile -t image_files < <(find "${SOURCE_DIR}" -maxdepth 1 -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' -o -name '*.svg' \) | sort)

if [[ "${#image_files[@]}" -eq 0 ]]; then
  echo "No image files found in ${SOURCE_DIR}" >&2
  exit 1
fi

rsync_cmd=(
  gcloud storage rsync
  "${SOURCE_DIR}"
  "${DESTINATION_URI}"
  --recursive
  --delete-unmatched-destination-objects
  --exclude='(^|/)(\.gitkeep|\.DS_Store)$'
)

if [[ "${DRY_RUN}" == "true" ]]; then
  rsync_cmd+=(--dry-run)
fi

echo "Syncing feature assets"
echo "  source: ${SOURCE_DIR}"
echo "  destination: ${DESTINATION_URI}"
if [[ "${DRY_RUN}" == "true" ]]; then
  echo "  mode: dry-run"
fi

"${rsync_cmd[@]}"
