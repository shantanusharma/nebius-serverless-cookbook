#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root and the default .env path once, for all helper scripts.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${COOKBOOK_ENV_FILE:-$ROOT_DIR/.env}"

require_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing env file: $ENV_FILE"
    echo "Copy .env.example to .env and fill required values."
    exit 1
  fi
}

load_env() {
  require_env_file
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
}

# save_env KEY VALUE
# Idempotent update-or-append into $ENV_FILE. Always prints what was saved
# so the caller can see exactly which variables changed.
save_env() {
  local key="$1"
  local value="$2"
  require_env_file
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
  echo "  Saved ${key}=${value} to ${ENV_FILE}"
}

require_cmd() {
  local c="$1"
  if ! command -v "$c" >/dev/null 2>&1; then
    echo "Missing command: $c"
    exit 1
  fi
}

json_get() {
  jq -r "$1"
}

# nebius_capture_json OUT_VAR  -- args to nebius (e.g. "ai" "job" "create" ...)
#
# Defensive replacement for `JSON="$(nebius ... --format json)"`.
# Handles CLI output that is prefixed with warnings/progress lines before the
# JSON object/array.
nebius_capture_json() {
  local out_var="$1"
  shift
  local stdout_f stderr_f
  stdout_f="$(mktemp)"
  stderr_f="$(mktemp)"
  set +e
  nebius "$@" >"$stdout_f" 2>"$stderr_f"
  local rc=$?
  set -e

  if (( rc != 0 )); then
    echo "  ✗ 'nebius $*' failed (exit $rc):" >&2
    head -c 2048 "$stderr_f" >&2
    echo "" >&2
    rm -f "$stdout_f" "$stderr_f"
    return 1
  fi

  local cleaned
  cleaned="$(awk '/^[[:space:]]*[{[]/{p=1} p{print}' "$stdout_f")"

  if [[ -z "$cleaned" ]] || ! printf '%s' "$cleaned" | jq -e . >/dev/null 2>&1; then
    echo "  ✗ Could not parse 'nebius $*' output as JSON." >&2
    echo "    --- stdout (first 1KB) ---" >&2
    head -c 1024 "$stdout_f" >&2
    echo "" >&2
    if [[ -s "$stderr_f" ]]; then
      echo "    --- stderr (first 1KB) ---" >&2
      head -c 1024 "$stderr_f" >&2
      echo "" >&2
    fi

    # Fallback: some CLI versions ignore --format json for create and emit a
    # human-readable summary that still contains the resource ID. Detect ID,
    # then fetch JSON via `nebius ... get --format json`.
    local kind="" id_pattern="" id=""
    if [[ "${1:-}" == "ai" && "${2:-}" == "endpoint" ]]; then
      kind="ai endpoint"
      id_pattern='aiendpoint-[a-z0-9]+'
    elif [[ "${1:-}" == "ai" && "${2:-}" == "job" ]]; then
      kind="ai job"
      id_pattern='aijob-[a-z0-9]+'
    fi

    if [[ -n "$kind" && -n "$id_pattern" ]]; then
      id="$(grep -Eo "$id_pattern" "$stdout_f" | head -n 1 || true)"
      if [[ -n "$id" ]]; then
        local fetched
        fetched="$(nebius ${kind} get "$id" --format json 2>/dev/null || true)"
        if [[ -n "$fetched" ]] && printf '%s' "$fetched" | jq -e . >/dev/null 2>&1; then
          printf -v "$out_var" '%s' "$fetched"
          rm -f "$stdout_f" "$stderr_f"
          echo "    ✓ Parsed via fallback: used ${kind} get $id" >&2
          return 0
        fi
      fi
    fi

    rm -f "$stdout_f" "$stderr_f"
    return 2
  fi

  printf -v "$out_var" '%s' "$cleaned"
  rm -f "$stdout_f" "$stderr_f"
  return 0
}

# resolve_resource_id KIND OUT_VAR ID_VAR NAME_VAR
# Hybrid resolver: prefers a known ID, falls back to name lookup, refuses to
# guess on duplicates.
resolve_resource_id() {
  local kind="$1" out_var="$2" id_var="$3" name_var="$4"
  local id_val=""
  local name_val="${!name_var:-}"
  if [[ -n "$id_var" && "$id_var" != "-" ]]; then
    id_val="${!id_var:-}"
  fi

  # 1. ID first
  if [[ -n "$id_val" ]] && nebius ${kind} get "$id_val" --format json >/dev/null 2>&1; then
    printf -v "$out_var" '%s' "$id_val"
    return 0
  fi

  # 2. Name fallback
  if [[ -z "$name_val" ]]; then
    printf -v "$out_var" '%s' ''
    return 1
  fi

  local parent_id="${PROJECT_ID:-}"
  local items
  if [[ -n "$parent_id" ]]; then
    items="$(nebius ${kind} list --parent-id "$parent_id" --format json 2>/dev/null \
      | jq -r --arg n "$name_val" '.items[]? | select(.metadata.name == $n) | .metadata.id')"
  else
    items="$(nebius ${kind} list --format json 2>/dev/null \
      | jq -r --arg n "$name_val" '.items[]? | select(.metadata.name == $n) | .metadata.id')"
  fi

  local count
  count="$(printf '%s\n' "$items" | grep -c . || true)"

  case "$count" in
    1)
      printf -v "$out_var" '%s' "$items"
      return 0
      ;;
    0)
      printf -v "$out_var" '%s' ''
      return 1
      ;;
    *)
      echo "" >&2
      echo "  ✗ Multiple ${kind} resources named '$name_val' in project ${PROJECT_ID:-<unknown>}:" >&2
      printf '      %s\n' $items >&2
      echo "" >&2
      if [[ -n "$id_var" && "$id_var" != "-" ]]; then
        echo "    Pin the one you want by setting ${id_var}=<id> in .env, or delete duplicates." >&2
      else
        echo "    Delete the duplicate(s) and re-run." >&2
      fi
      exit 1
      ;;
  esac
}

resolve_project_id() {
  local from_env="${PROJECT_ID:-}"
  if [[ -n "$from_env" && "$from_env" != "project-xxxxxxxxxxxxxxxx" ]]; then
    echo "$from_env"
    return 0
  fi

  local from_cli
  from_cli="$(nebius config get parent-id 2>/dev/null || true)"
  if [[ -n "$from_cli" ]]; then
    echo "$from_cli"
    return 0
  fi

  echo "Unable to resolve project id." >&2
  echo "Set PROJECT_ID in .env or run:" >&2
  echo "  nebius profile create" >&2
  echo "  nebius config set parent-id <project_id>" >&2
  return 1
}

resolve_subnet_id() {
  local parent_id="${PROJECT_ID:-}"
  if [[ -z "$parent_id" ]]; then
    parent_id="$(nebius config get parent-id 2>/dev/null || true)"
  fi
  if [[ -z "$parent_id" ]]; then
    echo "Cannot resolve subnet: PROJECT_ID is empty and 'nebius config get parent-id' returned nothing." >&2
    return 1
  fi

  local from_env="${SUBNET_ID:-}"
  if [[ -n "$from_env" && "$from_env" != "subnet-xxxxxxxxxxxxxxxx" ]]; then
    local actual_parent
    actual_parent="$(nebius vpc subnet get "$from_env" --format json 2>/dev/null | jq -r '.metadata.parent_id // ""' || true)"
    if [[ -n "$actual_parent" && "$actual_parent" != "$parent_id" ]]; then
      echo "  ✗ SUBNET_ID=$from_env belongs to project $actual_parent, but PROJECT_ID=$parent_id" >&2
      echo "    Remove SUBNET_ID from .env to auto-pick a subnet from the correct project," >&2
      echo "    or set SUBNET_ID to a subnet that lives in $parent_id." >&2
      return 1
    fi
    echo "$from_env"
    return 0
  fi

  local from_cli
  from_cli="$(nebius vpc subnet list --parent-id "$parent_id" --format json 2>/dev/null | jq -r '.items[0].metadata.id // ""' || true)"
  if [[ -n "$from_cli" ]]; then
    echo "$from_cli"
    return 0
  fi

  echo "Unable to resolve subnet id in project ${parent_id}." >&2
  echo "Set SUBNET_ID in .env or create a subnet in Nebius." >&2
  return 1
}

# is_force_mode "$@"
# Returns 0 if `--force` / `-f` is passed in args, or FORCE=1 in env.
is_force_mode() {
  [[ "${FORCE:-}" == "1" ]] && return 0
  local a
  for a in "$@"; do
    [[ "$a" == "--force" || "$a" == "-f" ]] && return 0
  done
  return 1
}

# banner "Description"
banner() {
  local desc="$1"
  echo ""
  echo "================================================================"
  echo "  ${desc}"
  echo "================================================================"
}
