#!/usr/bin/env bash

# Local script run with S3 config

# Exit on error
set -e

# Prevent sourcing; must be executed as a script
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "Do not source this script. Run it: bash ./scripts/run_docker.sh [--debug] <PROTEIN_ID> <STEPS>" >&2
  return 1 2>/dev/null || exit 1
fi

DEBUG_MODE=false
POSITIONAL_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --debug)
      DEBUG_MODE=true
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/run_docker.sh [--debug] [PROTEIN_ID] [STEPS]

Modes:
  default  Strict validation, exits if required env vars are missing.
  --debug  Continues with warnings even if env vars are missing.
EOF
      exit 0
      ;;
    *)
      POSITIONAL_ARGS+=("$arg")
      ;;
  esac
done

PROTEIN_ID=${POSITIONAL_ARGS[0]:-"1UBQ"}
STEPS=${POSITIONAL_ARGS[1]:-"100"}
DEFAULT_IMAGE="mnrozhkov/openmm-serverless:v0.1.5"
IMAGE_TAG=${IMAGE_TAG:-"v0.1.5"}
CONTAINER_REGISTRY_PATH=${CONTAINER_REGISTRY_PATH:-""}

if [ -z "${IMAGE:-}" ]; then
    if [ -n "$CONTAINER_REGISTRY_PATH" ]; then
        IMAGE="${CONTAINER_REGISTRY_PATH}/openmm-serverless:${IMAGE_TAG}"
    else
        IMAGE="$DEFAULT_IMAGE"
    fi
fi


echo "Running OpenMM simulation for protein $PROTEIN_ID with $STEPS steps"
if [ "$DEBUG_MODE" = true ]; then
  echo "Mode: debug (warnings only for missing env vars)"
else
  echo "Mode: default (strict env var validation)"
fi


# Check if required environment variables are set
echo "Checking environment variables..."
required_vars=(
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_DEFAULT_REGION"
    "S3_BUCKET"
    "S3_PREFIX"
    "S3_ENDPOINT_URL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
        if [ "$DEBUG_MODE" = true ]; then
            echo "⚠️  $var is not set"
        else
            echo "❌ $var is not set"
        fi
    else
        echo "✅ $var is set"
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    if [ "$DEBUG_MODE" = true ]; then
        echo "⚠️  Continuing in debug mode with missing variables: ${missing_vars[*]}" >&2
    else
        echo "Missing required environment variables: ${missing_vars[*]}" >&2
        exit 1
    fi
fi

echo "Using image: $IMAGE"

# Pull the image if it is not already available locally
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker pull "$IMAGE"
fi

# Test local
docker run --platform linux/amd64 --rm \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  -e S3_BUCKET="$S3_BUCKET" \
  -e S3_PREFIX="$S3_PREFIX" \
  -e S3_ENDPOINT_URL="$S3_ENDPOINT_URL" \
  "$IMAGE" "$PROTEIN_ID" "$STEPS"

echo "Simulation completed!"