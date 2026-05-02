#!/usr/bin/env bash
# Source this file in any new terminal to load the cookbook env vars:
#   source scripts/activate.sh
#
# Required when you want to run manual `nebius ai ...` / `curl` / `aws s3`
# commands in a fresh terminal — the helper scripts load .env themselves.

# Resolve repo root from the location of this file.
# - bash: BASH_SOURCE[0]
# - zsh:  ${(%):-%N} (path of sourced file)
# - fallback: $0
__COOKBOOK_SOURCE="${BASH_SOURCE[0]:-}"
if [[ -z "${__COOKBOOK_SOURCE}" && -n "${ZSH_VERSION:-}" ]]; then
  __COOKBOOK_SOURCE="${(%):-%N}"
fi
__COOKBOOK_SOURCE="${__COOKBOOK_SOURCE:-$0}"
__COOKBOOK_ROOT="$(cd "$(dirname "${__COOKBOOK_SOURCE}")/.." && pwd)"
__COOKBOOK_ENV="${COOKBOOK_ENV_FILE:-${__COOKBOOK_ROOT}/.env}"

if [[ ! -f "${__COOKBOOK_ENV}" ]]; then
  echo "Missing env file: ${__COOKBOOK_ENV}"
  echo "Run: bash scripts/bootstrap-env.sh"
  unset __COOKBOOK_ROOT __COOKBOOK_ENV __COOKBOOK_SOURCE
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck source=/dev/null
source "${__COOKBOOK_ENV}"
set +a

echo "Cookbook env loaded from ${__COOKBOOK_ENV}"
echo "Key values:"
echo "  PROJECT_ID=${PROJECT_ID:-<not set>}"
echo "  SUBNET_ID=${SUBNET_ID:-<not set>}"
echo "  BUCKET_NAME=${BUCKET_NAME:-<not set>}"
echo "  BUCKET_ID=${BUCKET_ID:-<not set>}"
echo "  S3_ENDPOINT_URL=${S3_ENDPOINT_URL:-<not set>}"
echo "  AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:+<set>}${AWS_ACCESS_KEY_ID:-<not set>}"

unset __COOKBOOK_ROOT __COOKBOOK_ENV __COOKBOOK_SOURCE
