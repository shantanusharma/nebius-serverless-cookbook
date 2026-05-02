#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Nothing to clean. If you created resources manually, delete them via the Nebius console/CLI."
  exit 0
fi

load_env

ASSUME_YES="${ASSUME_YES:-0}"
TARGET_JOB_NAME=""
TARGET_ENDPOINT_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --job)
      TARGET_JOB_NAME="$2"
      shift 2
      ;;
    --endpoint)
      TARGET_ENDPOINT_NAME="$2"
      shift 2
      ;;
    -y|--assume-yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/cleanup.sh [--job NAME] [--endpoint NAME] [--assume-yes]

Deletes:
  - Bucket from .env (empties via AWS CLI if available)
  - Service account "cookbook-storage-sa"
  - Optionally: job by name (from --job), endpoint by name (from --endpoint)

Flags:
  --job NAME        Delete ai job named NAME (uses .env JOB_ID if set)
  --endpoint NAME   Delete ai endpoint named NAME (uses .env ENDPOINT_ID if set)
  -y, --assume-yes  Skip confirmations (or set ASSUME_YES=1)
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

banner "Cleanup -- delete toolkit resources"

require_cmd nebius
require_cmd jq

confirm() {
  local prompt="$1"
  if [[ "$ASSUME_YES" == "1" ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]]
}

delete_endpoint_if_exists() {
  local name_var="$1" id_var="$2"
  local name_val="${!name_var:-}"
  local id_val="${!id_var:-}"
  local id=""
  if [[ -z "$name_val" && -z "$id_val" ]]; then
    echo "  • Endpoint: nothing to delete"
    return
  fi
  resolve_resource_id 'ai endpoint' id "$id_var" "$name_var" || true
  if [[ -z "$id" ]]; then
    echo "  • Endpoint: not found, nothing to delete"
    return
  fi
  if confirm "Delete endpoint ${id}?"; then
    nebius ai endpoint delete "$id" || true
    echo "  ✓ Deleted endpoint ${id}"
  else
    echo "  • Skipped endpoint ${id}"
  fi
}

delete_job_if_exists() {
  local name_var="$1" id_var="$2"
  local name_val="${!name_var:-}"
  local id_val="${!id_var:-}"
  local id=""
  if [[ -z "$name_val" && -z "$id_val" ]]; then
    echo "  • Job: nothing to delete"
    return
  fi
  resolve_resource_id 'ai job' id "$id_var" "$name_var" || true
  if [[ -z "$id" ]]; then
    echo "  • Job: not found, nothing to delete"
    return
  fi
  if confirm "Delete job ${id}?"; then
    nebius ai job delete "$id" || true
    echo "  ✓ Deleted job ${id}"
  else
    echo "  • Skipped job ${id}"
  fi
}

delete_bucket_if_exists() {
  local name="${BUCKET_NAME:-}"
  local id="${BUCKET_ID:-}"
  if [[ -z "$name" && -z "$id" ]]; then
    echo "  • Bucket: nothing to delete"
    return
  fi
  resolve_resource_id 'storage bucket' id BUCKET_ID BUCKET_NAME || true
  if [[ -z "$id" ]]; then
    echo "  • Bucket ${name:-<unspecified>}: not found, nothing to delete"
    return
  fi
  if ! confirm "Empty + delete bucket ${name:-<unnamed>} (${id})?"; then
    echo "  • Skipped bucket ${name:-<unnamed>}"
    return
  fi
  if command -v aws >/dev/null 2>&1; then
    local endpoint="${S3_ENDPOINT_URL:-}"
    if [[ -z "$endpoint" && -n "${NEBIUS_REGION:-}" ]]; then
      endpoint="https://storage.${NEBIUS_REGION}.nebius.cloud"
    fi
    echo "  Emptying bucket ${name}..."
    if [[ -n "$endpoint" ]]; then
      aws s3 rm "s3://${name}" --recursive --endpoint-url "$endpoint" || true
    else
      aws s3 rm "s3://${name}" --recursive || true
    fi
  fi
  nebius storage bucket delete --id "$id" || true
  echo "  ✓ Deleted bucket ${name:-<unnamed>}"
}

delete_service_account() {
  local sa_name="cookbook-storage-sa"
  local sa_id=""
  resolve_resource_id 'iam service-account' sa_id - sa_name || true
  if [[ -z "$sa_id" ]]; then
    echo "  • Service account: nothing to delete"
    return
  fi
  if confirm "Delete service account ${sa_name} (${sa_id})?"; then
    nebius iam service-account delete "$sa_id" || true
    echo "  ✓ Deleted service account ${sa_id}"
  else
    echo "  • Skipped service account ${sa_id}"
  fi
}

echo "This will delete the toolkit bucket and service account."
echo "Pass --job NAME and/or --endpoint NAME to delete those as well."
echo ""

delete_endpoint_if_exists TARGET_ENDPOINT_NAME ENDPOINT_ID
delete_job_if_exists TARGET_JOB_NAME JOB_ID
delete_bucket_if_exists
delete_service_account

echo ""
echo "  ✓ Cleanup pass complete."
echo "    Note: .env still holds previous IDs/tokens. Wipe keys manually if starting fresh."
