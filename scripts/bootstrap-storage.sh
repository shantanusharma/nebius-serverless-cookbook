#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Run: bash scripts/bootstrap-env.sh"
  exit 1
fi

load_env

banner "Bootstrap object storage (bucket + AWS credentials)"

require_cmd nebius
require_cmd aws
require_cmd jq
require_cmd openssl

PROJECT_ID="$(resolve_project_id)"
NEBIUS_REGION="${NEBIUS_REGION:-eu-north1}"
save_env NEBIUS_REGION "$NEBIUS_REGION"

# Optional args:
#   $1 bucket name prefix (default: cookbook)
#   $2 object prefix (S3_PREFIX). If unset, uses existing S3_PREFIX or "cookbook".
NAME_PREFIX="${1:-cookbook}"
S3_PREFIX="${2:-${S3_PREFIX:-cookbook}}"

# ── Bucket name (auto-generated if not pinned) ──────────────
if [[ -z "${BUCKET_NAME:-}" || "${BUCKET_NAME:-}" == "workshop-llm" ]]; then
  RAND_SUFFIX="$(openssl rand -hex 3)"
  BUCKET_NAME="${NAME_PREFIX}-${RAND_SUFFIX}"
  echo "  ℹ  Auto-generated bucket name: $BUCKET_NAME (prefix=${NAME_PREFIX})"
  save_env BUCKET_NAME "$BUCKET_NAME"
fi

echo ""
echo "── Setting up object storage ──────────────────────────"
if resolve_resource_id 'storage bucket' BUCKET_ID BUCKET_ID BUCKET_NAME; then
  echo "  ✓ Bucket already exists: $BUCKET_NAME ($BUCKET_ID)"
else
  echo "  Creating bucket: $BUCKET_NAME"
  nebius storage bucket create \
    --name "$BUCKET_NAME" \
    --parent-id "$PROJECT_ID"
  resolve_resource_id 'storage bucket' BUCKET_ID BUCKET_ID BUCKET_NAME
  echo "  ✓ Bucket created: $BUCKET_NAME ($BUCKET_ID)"
fi
save_env BUCKET_ID "$BUCKET_ID"

# ── Create service account + access key ─────────────────────
SA_NAME="cookbook-storage-sa"
TENANT_ID="$(nebius iam project get "$PROJECT_ID" --format json | json_get '.metadata.parent_id')"
EDITORS_GROUP_ID="$(nebius iam group get-by-name --name editors --parent-id "$TENANT_ID" --format json | json_get '.metadata.id')"

if resolve_resource_id 'iam service-account' SA_ID - SA_NAME; then
  echo "  ✓ Service account exists: $SA_ID"
else
  echo "  Creating service account: $SA_NAME"
  SA_ID="$(nebius iam service-account create \
    --name "$SA_NAME" \
    --parent-id "$PROJECT_ID" \
    --format jsonpath='{.metadata.id}')"
  nebius iam group-membership create \
    --parent-id "$EDITORS_GROUP_ID" \
    --member-id "$SA_ID" >/dev/null
  echo "  ✓ Service account created: $SA_ID"
fi

echo "  Creating access key..."
ACCESS_KEY_JSON="$(nebius iam v2 access-key create \
  --account-service-account-id "$SA_ID" \
  --description 'AWS CLI cookbook' \
  --format json)"

AWS_ACCESS_KEY_ID="$(echo "$ACCESS_KEY_JSON"   | jq -r '.status.aws_access_key_id')"
AWS_SECRET_ACCESS_KEY="$(echo "$ACCESS_KEY_JSON" | jq -r '.status.secret')"
echo "  ✓ Access key created"

# ── Configure AWS CLI ───────────────────────────────────────
aws configure set aws_access_key_id     "$AWS_ACCESS_KEY_ID"
aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY"
aws configure set region "${NEBIUS_REGION}"
echo "  ✓ AWS CLI configured for Nebius S3 (region: ${NEBIUS_REGION})"

# ── Persist env vars ────────────────────────────────────────
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-https://storage.${NEBIUS_REGION}.nebius.cloud}"

save_env S3_BUCKET "$BUCKET_NAME"
save_env BUCKET_ID "$BUCKET_ID"
save_env S3_PREFIX "$S3_PREFIX"
save_env S3_ENDPOINT_URL "$S3_ENDPOINT_URL"
save_env AWS_ACCESS_KEY_ID "$AWS_ACCESS_KEY_ID"
save_env AWS_SECRET_ACCESS_KEY "$AWS_SECRET_ACCESS_KEY"
save_env AWS_DEFAULT_REGION "$NEBIUS_REGION"

echo ""
echo "  ✓ Storage bootstrap done"
echo "    project_id=$PROJECT_ID"
echo "    bucket=$BUCKET_NAME ($BUCKET_ID)"
echo "    service_account_id=$SA_ID"
echo ""
echo "Next: run your example, or bash scripts/cleanup.sh to tear down"
