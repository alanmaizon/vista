#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-${1:-}}"
if [[ -z "${PROJECT_ID}" ]]; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
fi
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: No project set. Pass PROJECT_ID as the first argument or export PROJECT_ID."
  exit 1
fi

TEST_REGIONS_INPUT="${TEST_REGIONS:-us-central1 us-east5 europe-west4}"
TEST_REGIONS_INPUT="${TEST_REGIONS_INPUT//,/ }"
read -r -a TEST_REGIONS <<<"${TEST_REGIONS_INPUT}"

SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-lyria-access-check}"
SERVICE_ACCOUNT_DISPLAY_NAME="${SERVICE_ACCOUNT_DISPLAY_NAME:-Lyria Access Check}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KNOWN_MODEL_REGION="${KNOWN_MODEL_REGION:-us-central1}"
KNOWN_MODEL_ID="${KNOWN_MODEL_ID:-lyria-002}"
KNOWN_MODEL_RESOURCE="publishers/google/models/${KNOWN_MODEL_ID}"

REQUIRED_APIS=(
  "aiplatform.googleapis.com"
  "iam.googleapis.com"
  "cloudresourcemanager.googleapis.com"
)

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: Required command not found: $1"
    exit 1
  fi
}

run_capture() {
  local outfile="$1"
  shift
  local rc
  set +e
  "$@" >"${outfile}" 2>&1
  rc=$?
  set -e
  return "${rc}"
}

help_contains() {
  local pattern="$1"
  shift
  local help_out rc
  set +e
  help_out="$("$@" --help 2>&1)"
  rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]]; then
    return 1
  fi
  printf '%s\n' "${help_out}" | grep -qi -- "${pattern}"
}

join_by() {
  local sep="$1"
  shift
  local first=1
  local item
  for item in "$@"; do
    if [[ "${first}" -eq 1 ]]; then
      printf '%s' "${item}"
      first=0
    else
      printf '%s%s' "${sep}" "${item}"
    fi
  done
}

member_type_for_account() {
  local account="$1"
  if [[ "${account}" == *".gserviceaccount.com" ]]; then
    printf 'serviceAccount:%s' "${account}"
  else
    printf 'user:%s' "${account}"
  fi
}

project_roles_for_member() {
  local member="$1"
  gcloud projects get-iam-policy "${PROJECT_ID}" \
    --flatten="bindings[].members" \
    --filter="bindings.members=${member}" \
    --format="value(bindings.role)" 2>/dev/null | sort -u || true
}

has_aiplatform_user_or_broader() {
  local roles_blob="$1"
  if printf '%s\n' "${roles_blob}" | grep -Eq '^(roles/aiplatform\.user|roles/aiplatform\.admin|roles/owner|roles/editor)$'; then
    return 0
  fi
  return 1
}

print_roles_for_principal() {
  local label="$1"
  local member="$2"
  local roles
  roles="$(project_roles_for_member "${member}")"

  echo "${label} principal: ${member}"
  if [[ -n "${roles}" ]]; then
    printf '%s\n' "${roles}" | sed 's/^/  role: /'
  else
    echo "  role: (no direct project-level roles found)"
  fi

  if has_aiplatform_user_or_broader "${roles}"; then
    echo "  has roles/aiplatform.user or broader: yes"
  else
    echo "  has roles/aiplatform.user or broader: no"
  fi
}

short_excerpt() {
  local file="$1"
  tr '\r\n' ' ' <"${file}" | sed 's/[[:space:]]\+/ /g' | cut -c1-260
}

extract_lyria_ids_from_file() {
  local file="$1"
  if [[ ! -s "${file}" ]]; then
    return 0
  fi
  grep -i 'lyria' "${file}" 2>/dev/null \
    | grep -Eio 'publishers/google/models/[^"[:space:],]+' 2>/dev/null \
    | sed 's#/$##' \
    | sort -u || true
}

rest_request() {
  local method="$1"
  local url="$2"
  local body_file="$3"
  local out_file="$4"
  local token status rc

  token="$(gcloud auth print-access-token 2>/dev/null || true)"
  if [[ -z "${token}" ]]; then
    printf '000'
    return 1
  fi

  local -a curl_args
  curl_args=(
    -sS
    -X "${method}"
    -H "Authorization: Bearer ${token}"
    -H "x-goog-user-project: ${PROJECT_ID}"
    -o "${out_file}"
    -w "%{http_code}"
  )

  if [[ -n "${body_file}" ]]; then
    curl_args+=(
      -H "Content-Type: application/json"
      --data-binary "@${body_file}"
    )
  fi

  curl_args+=("${url}")

  set +e
  status="$(curl "${curl_args[@]}")"
  rc=$?
  set -e

  if [[ "${rc}" -ne 0 ]]; then
    printf '000'
    return "${rc}"
  fi

  printf '%s' "${status}"
}

ensure_required_apis() {
  local missing=()
  local api enabled

  for api in "${REQUIRED_APIS[@]}"; do
    enabled="$(gcloud services list --enabled --project="${PROJECT_ID}" \
      --filter="config.name=${api}" \
      --format="value(config.name)" 2>/dev/null || true)"
    if [[ "${enabled}" != "${api}" ]]; then
      missing+=("${api}")
    fi
  done

  if [[ "${#missing[@]}" -eq 0 ]]; then
    echo "Required APIs already enabled."
    return 0
  fi

  echo "Enabling missing APIs: $(join_by ", " "${missing[@]}")"
  if gcloud services enable "${missing[@]}" --project="${PROJECT_ID}" >/dev/null; then
    echo "API enablement completed."
  else
    echo "WARNING: Failed to enable one or more APIs. Continuing."
  fi
}

ensure_service_account() {
  if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Service account already exists: ${SERVICE_ACCOUNT_EMAIL}"
    return 0
  fi

  echo "Creating service account: ${SERVICE_ACCOUNT_EMAIL}"
  if gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name="${SERVICE_ACCOUNT_DISPLAY_NAME}" \
    --project="${PROJECT_ID}" >/dev/null; then
    echo "Service account created."
  else
    echo "WARNING: Could not create service account (you might not have IAM admin rights). Continuing."
  fi
}

troubleshoot_permission() {
  local principal_email="$1"
  local resource_full_name="$2"
  local permission="$3"
  local out_file="$4"

  if help_contains "troubleshoot IAM allow and deny policies" gcloud policy-intelligence troubleshoot-policy iam; then
    run_capture "${out_file}" \
      gcloud policy-intelligence troubleshoot-policy iam "${resource_full_name}" \
      --principal-email="${principal_email}" \
      --permission="${permission}"
    return $?
  fi

  if help_contains "troubleshoot IAM allow and deny policies" gcloud beta policy-intelligence troubleshoot-policy iam; then
    run_capture "${out_file}" \
      gcloud beta policy-intelligence troubleshoot-policy iam "${resource_full_name}" \
      --principal-email="${principal_email}" \
      --permission="${permission}"
    return $?
  fi

  if help_contains "troubleshoot the IAM Policy" gcloud policy-troubleshoot iam; then
    run_capture "${out_file}" \
      gcloud policy-troubleshoot iam "${resource_full_name}" \
      --principal-email="${principal_email}" \
      --permission="${permission}"
    return $?
  fi

  if help_contains "troubleshoot the IAM Policy" gcloud beta policy-troubleshoot iam; then
    run_capture "${out_file}" \
      gcloud beta policy-troubleshoot iam "${resource_full_name}" \
      --principal-email="${principal_email}" \
      --permission="${permission}"
    return $?
  fi

  {
    echo "No supported gcloud policy troubleshooting command found."
    echo "Tried: gcloud policy-intelligence troubleshoot-policy iam"
    echo "Tried: gcloud beta policy-intelligence troubleshoot-policy iam"
    echo "Tried: gcloud policy-troubleshoot iam"
    echo "Tried: gcloud beta policy-troubleshoot iam"
  } >"${out_file}"
  return 2
}

discover_models_with_gcloud() {
  local out_file="$1"

  if help_contains "list the publisher models" gcloud ai model-garden models list; then
    run_capture "${out_file}" \
      gcloud ai model-garden models list \
      --model-filter=lyria \
      --full-resource-name \
      --project="${PROJECT_ID}" \
      --format="value(name)"
    return $?
  fi

  if help_contains "list the publisher models" gcloud beta ai model-garden models list; then
    run_capture "${out_file}" \
      gcloud beta ai model-garden models list \
      --model-filter=lyria \
      --full-resource-name \
      --project="${PROJECT_ID}" \
      --format="value(name)"
    return $?
  fi

  if help_contains "list the publisher models" gcloud alpha ai model-garden models list; then
    run_capture "${out_file}" \
      gcloud alpha ai model-garden models list \
      --model-filter=lyria \
      --full-resource-name \
      --project="${PROJECT_ID}" \
      --format="value(name)"
    return $?
  fi

  echo "No supported gcloud ai model-garden models list command found." >"${out_file}"
  return 2
}

callable_regions=()
permission_denied_regions=()
visible_not_callable_regions=()
no_model_regions=()
discovered_regions=()
known_model_fallback_regions=()
found_any_models=0
known_model_access_confirmed=0
gated_likely=0

require_cmd gcloud
require_cmd grep
require_cmd sed
require_cmd sort
require_cmd curl

echo "Setting gcloud project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

ensure_required_apis

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || true)"
if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
  ACTIVE_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
fi

echo "Active account: ${ACTIVE_ACCOUNT:-"(unknown)"}"
echo "Active project: ${PROJECT_ID}"
echo "Regions to test: $(join_by ", " "${TEST_REGIONS[@]}")"
echo

ensure_service_account

ACTIVE_MEMBER="$(member_type_for_account "${ACTIVE_ACCOUNT:-unknown}")"
SERVICE_ACCOUNT_MEMBER="serviceAccount:${SERVICE_ACCOUNT_EMAIL}"

echo "Project-level IAM roles:"
print_roles_for_principal "Active account" "${ACTIVE_MEMBER}"
print_roles_for_principal "Service account" "${SERVICE_ACCOUNT_MEMBER}"
echo

PREDICT_PERMISSION="aiplatform.endpoints.predict"
PREDICT_BODY_FILE="${TMP_DIR}/predict.json"
cat >"${PREDICT_BODY_FILE}" <<'JSON'
{
  "instances": [
    {
      "prompt": "Original ambient instrumental, soft synth pads, gentle pulse, no vocals, no resemblance to any known song."
    }
  ],
  "parameters": {}
}
JSON

for region in "${TEST_REGIONS[@]}"; do
  echo "============================================================"
  echo "Region: ${region}"

  region_candidates_file="${TMP_DIR}/${region}.candidates"
  : >"${region_candidates_file}"

  gcloud_list_out="${TMP_DIR}/${region}.gcloud_list.txt"
  if discover_models_with_gcloud "${gcloud_list_out}"; then
    gcloud_candidates="$(extract_lyria_ids_from_file "${gcloud_list_out}")"
    if [[ -n "${gcloud_candidates}" ]]; then
      echo "gcloud model listing exposed Lyria candidates (global listing via Model Garden):"
      printf '%s\n' "${gcloud_candidates}" | sed 's/^/  - /'
      printf '%s\n' "${gcloud_candidates}" >>"${region_candidates_file}"
    else
      echo "gcloud model listing ran, but no Lyria IDs were returned."
    fi
  else
    echo "gcloud model listing unavailable or failed: $(short_excerpt "${gcloud_list_out}")"
  fi

  rest_list_out="${TMP_DIR}/${region}.rest_list.json"
  rest_list_url="https://${region}-aiplatform.googleapis.com/v1beta1/publishers/google/models?filter=lyria&pageSize=50&view=PUBLISHER_MODEL_VIEW_BASIC&listAllVersions=true"
  rest_list_status="$(rest_request GET "${rest_list_url}" "" "${rest_list_out}" || true)"
  echo "Regional publisher model list HTTP status: ${rest_list_status}"
  if [[ "${rest_list_status}" == "200" ]]; then
    rest_candidates="$(extract_lyria_ids_from_file "${rest_list_out}")"
    if [[ -n "${rest_candidates}" ]]; then
      echo "Regional list exposed Lyria candidates:"
      printf '%s\n' "${rest_candidates}" | sed 's/^/  - /'
      printf '%s\n' "${rest_candidates}" >>"${region_candidates_file}"
    else
      echo "Regional list succeeded, but no Lyria IDs were visible in the response."
    fi
  elif [[ "${rest_list_status}" != "000" ]]; then
    echo "Regional list error: $(short_excerpt "${rest_list_out}")"
  else
    echo "Regional list could not be completed (curl/auth failure)."
  fi

  if [[ -s "${region_candidates_file}" ]]; then
    sort -u "${region_candidates_file}" -o "${region_candidates_file}"
  fi

  if [[ ! -s "${region_candidates_file}" ]]; then
    if [[ "${region}" == "${KNOWN_MODEL_REGION}" ]]; then
      echo "No Lyria IDs were visible via listing in ${region}."
      echo "Falling back to the documented model ID: ${KNOWN_MODEL_RESOURCE}"
      printf '%s\n' "${KNOWN_MODEL_RESOURCE}" >"${region_candidates_file}"
      known_model_fallback_regions+=("${region}")
    else
      echo "No Lyria models visible in ${region} (may be gated/allowlisted or unavailable in this region)."
      no_model_regions+=("${region}")
      continue
    fi
  fi

  found_any_models=1
  discovered_regions+=("${region}")
  candidate_model="$(head -n 1 "${region_candidates_file}")"
  short_model_id="${candidate_model#publishers/google/models/}"

  echo "Primary candidate selected for probe: ${candidate_model}"

  describe_out="${TMP_DIR}/${region}.describe.json"
  describe_url="https://${region}-aiplatform.googleapis.com/v1beta1/${candidate_model}?view=PUBLISHER_MODEL_VIEW_FULL"
  describe_status="$(rest_request GET "${describe_url}" "" "${describe_out}" || true)"
  echo "Describe model HTTP status: ${describe_status}"
  if [[ "${describe_status}" == "200" ]]; then
    echo "Model exists in ${region}."
    if grep -q 'predictSchemata' "${describe_out}" 2>/dev/null; then
      echo "Describe response includes predictSchemata."
    fi
    if grep -q 'supportedActions' "${describe_out}" 2>/dev/null; then
      echo "Describe response includes supportedActions."
    fi
  elif [[ "${describe_status}" != "000" ]]; then
    echo "Describe call error: $(short_excerpt "${describe_out}")"
  else
    echo "Describe call could not be completed (curl/auth failure)."
  fi

  predict_out="${TMP_DIR}/${region}.predict.json"
  predict_url="https://${region}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${region}/${candidate_model}:predict"
  predict_status="$(rest_request POST "${predict_url}" "${PREDICT_BODY_FILE}" "${predict_out}" || true)"
  echo "Predict probe HTTP status: ${predict_status}"

  case "${predict_status}" in
    200)
      echo "Predict probe succeeded."
      callable_regions+=("${region}")
      if [[ "${region}" == "${KNOWN_MODEL_REGION}" && "${candidate_model}" == "${KNOWN_MODEL_RESOURCE}" ]]; then
        known_model_access_confirmed=1
      fi
      ;;
    400|422)
      if grep -qi 'recitation checks' "${predict_out}" 2>/dev/null; then
        echo "Predict endpoint reached the model, but the response was blocked by recitation checks. This confirms Lyria access."
      else
        echo "Predict endpoint responded, but the request was rejected. This still suggests the model surface is callable."
      fi
      echo "Predict probe response: $(short_excerpt "${predict_out}")"
      callable_regions+=("${region}")
      if [[ "${region}" == "${KNOWN_MODEL_REGION}" && "${candidate_model}" == "${KNOWN_MODEL_RESOURCE}" ]]; then
        known_model_access_confirmed=1
      fi
      ;;
    403)
      echo "Predict probe was denied. The model is visible but not callable with the current principal or policy."
      echo "Predict probe response: $(short_excerpt "${predict_out}")"
      permission_denied_regions+=("${region}")
      ;;
    404|405)
      echo "Generic predict probe was not accepted. The model may use a specialized action or a different surface."
      echo "Predict probe response: $(short_excerpt "${predict_out}")"
      visible_not_callable_regions+=("${region}")
      ;;
    000)
      echo "Predict probe could not be completed (curl/auth failure)."
      visible_not_callable_regions+=("${region}")
      ;;
    *)
      echo "Predict probe returned an unexpected status."
      echo "Predict probe response: $(short_excerpt "${predict_out}")"
      visible_not_callable_regions+=("${region}")
      ;;
  esac

  model_resource_full_name="//aiplatform.googleapis.com/projects/${PROJECT_ID}/locations/${region}/publishers/google/models/${short_model_id}"
  echo "Policy troubleshoot target: ${model_resource_full_name}"

  user_troubleshoot_out="${TMP_DIR}/${region}.user.troubleshoot.txt"
  if troubleshoot_permission "${ACTIVE_ACCOUNT}" "${model_resource_full_name}" "${PREDICT_PERMISSION}" "${user_troubleshoot_out}"; then
    echo "Policy troubleshoot (active user):"
    sed 's/^/  /' "${user_troubleshoot_out}"
  else
    echo "Policy troubleshoot (active user) could not complete:"
    sed 's/^/  /' "${user_troubleshoot_out}"
  fi

  sa_troubleshoot_out="${TMP_DIR}/${region}.sa.troubleshoot.txt"
  if troubleshoot_permission "${SERVICE_ACCOUNT_EMAIL}" "${model_resource_full_name}" "${PREDICT_PERMISSION}" "${sa_troubleshoot_out}"; then
    echo "Policy troubleshoot (service account):"
    sed 's/^/  /' "${sa_troubleshoot_out}"
  else
    echo "Policy troubleshoot (service account) could not complete:"
    sed 's/^/  /' "${sa_troubleshoot_out}"
  fi
done

echo "============================================================"
echo "Final summary"
echo "Regions tested: $(join_by ", " "${TEST_REGIONS[@]}")"

if [[ "${found_any_models}" -eq 1 ]]; then
  echo "Lyria model IDs discovered: yes"
  echo "Regions with discovered IDs: $(join_by ", " "${discovered_regions[@]}")"
else
  echo "Lyria model IDs discovered: no"
fi

if [[ "${#callable_regions[@]}" -gt 0 ]]; then
  echo "Regions with callable or callable-ish response: $(join_by ", " "${callable_regions[@]}")"
fi

if [[ "${#permission_denied_regions[@]}" -gt 0 ]]; then
  echo "Regions where models were visible but predict was denied: $(join_by ", " "${permission_denied_regions[@]}")"
fi

if [[ "${#visible_not_callable_regions[@]}" -gt 0 ]]; then
  echo "Regions where models were visible but generic predict was not confirmed: $(join_by ", " "${visible_not_callable_regions[@]}")"
fi

if [[ "${#no_model_regions[@]}" -gt 0 ]]; then
  echo "Regions with no visible Lyria models: $(join_by ", " "${no_model_regions[@]}")"
fi

if [[ "${#known_model_fallback_regions[@]}" -gt 0 ]]; then
  echo "Known-model fallback used in: $(join_by ", " "${known_model_fallback_regions[@]}")"
fi

if [[ "${known_model_access_confirmed}" -eq 1 ]]; then
  echo "Direct ${KNOWN_MODEL_ID} probe in ${KNOWN_MODEL_REGION} confirmed access: yes"
fi

if [[ "${found_any_models}" -eq 0 && "${known_model_access_confirmed}" -eq 0 && "${#permission_denied_regions[@]}" -eq 0 && "${#visible_not_callable_regions[@]}" -eq 0 && "${#callable_regions[@]}" -eq 0 ]]; then
  gated_likely=1
fi

if [[ "${gated_likely}" -eq 1 ]]; then
  echo "Assessment: The project appears gated, allowlisted out, or the tested regions do not currently expose Lyria."
elif [[ "${#permission_denied_regions[@]}" -gt 0 && "${#callable_regions[@]}" -eq 0 ]]; then
  echo "Assessment: Lyria models are visible, but the current principal or policy appears to block calling them."
elif [[ "${#callable_regions[@]}" -gt 0 ]]; then
  echo "Assessment: At least one tested region appears to expose a callable Lyria model surface."
else
  echo "Assessment: Lyria visibility was mixed; some regions exposed metadata but generic predict was not confirmed."
fi

echo "Next actions:"
if [[ "${gated_likely}" -eq 1 ]]; then
  echo "- Request Lyria access or allowlisting if this model is restricted for your project."
  echo "- Try additional regions and rerun with TEST_REGIONS=\"...\"."
  echo "- Check org policy constraints such as vertexai.allowedModels."
elif [[ "${#permission_denied_regions[@]}" -gt 0 && "${#callable_regions[@]}" -eq 0 ]]; then
  echo "- Grant roles/aiplatform.user (or broader) to the caller and/or service account."
  echo "- Check org policy constraints such as vertexai.allowedModels and any deny policies."
  echo "- Re-run policy troubleshooting against the visible model resource."
elif [[ "${#callable_regions[@]}" -gt 0 ]]; then
  echo "- Use one of the callable regions above for your first real integration test."
  echo "- If you see recitation-check 400s, use a more original prompt and avoid lyrics or recognizable melodies."
  echo "- Keep probing ${KNOWN_MODEL_ID} in ${KNOWN_MODEL_REGION}; listing may stay empty even when direct access works."
  echo "- Confirm the exact request schema from the current Lyria model card before production use."
else
  echo "- Verify whether the model requires a specialized method instead of generic :predict."
  echo "- Check the model card or API docs for the exact action name and request schema."
  echo "- Confirm that org policy and IAM are not restricting Model Garden access."
fi
