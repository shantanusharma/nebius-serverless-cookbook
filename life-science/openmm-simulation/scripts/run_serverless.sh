#!/bin/bash

# Submit an OpenMM simulation as a Nebius AI Job.

set -e

DEBUG_MODE=false
POSITIONAL_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --debug)
            DEBUG_MODE=true
            ;;
        -h|--help)
            cat <<'EOF'
Usage: ./scripts/run_serverless.sh [--debug] [PROTEIN_ID] [STEPS]

Modes:
  default  Strict validation, exits if required env vars are missing.
  --debug  Continues with warnings when S3 env vars are missing.
EOF
            exit 0
            ;;
        *)
            POSITIONAL_ARGS+=("$arg")
            ;;
    esac
done

PROTEIN_ID=${POSITIONAL_ARGS[0]:-"1UBQ"}
STEPS=${POSITIONAL_ARGS[1]:-"1000"}
DEFAULT_IMAGE="mnrozhkov/openmm-serverless:v0.1.5"
IMAGE_TAG=${IMAGE_TAG:-"v0.1.5"}
IMAGE=${IMAGE:-""}
CONTAINER_REGISTRY_PATH=${CONTAINER_REGISTRY_PATH:-""}
JOB_PLATFORM=${JOB_PLATFORM:-"gpu-l40s-a"}
JOB_PRESET=${JOB_PRESET:-"1gpu-8vcpu-32gb"}
JOB_TIMEOUT=${JOB_TIMEOUT:-"4h"}
SUBNET_ID=${SUBNET_ID:-""}

echo "Submitting OpenMM simulation for protein $PROTEIN_ID with $STEPS steps"
if [ "$DEBUG_MODE" = true ]; then
    echo "Mode: debug (S3 env vars optional; results may be lost after job completion)"
else
    echo "Mode: default (strict S3 env var validation)"
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

if [ -z "$IMAGE" ]; then
    if [ -n "$CONTAINER_REGISTRY_PATH" ]; then
        IMAGE="${CONTAINER_REGISTRY_PATH}/openmm-serverless:${IMAGE_TAG}"
    else
        IMAGE="$DEFAULT_IMAGE"
    fi
fi
echo "Using image: $IMAGE"
PROTEIN_ID_LOWER="$(printf '%s' "$PROTEIN_ID" | tr '[:upper:]' '[:lower:]')"
JOB_NAME="openmm-${PROTEIN_ID_LOWER}-${STEPS}-$(date +%Y%m%d%H%M%S)"
ARGS="--protein-id ${PROTEIN_ID} --steps ${STEPS}"

CREATE_CMD=(
  nebius ai job create
  --name "$JOB_NAME"
  --image "$IMAGE"
  --preset "$JOB_PRESET"
  --timeout "$JOB_TIMEOUT"
  --args "$ARGS"
  --format "jsonpath={.metadata.id}"
  --disk-size 450Gi
)

if [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
  CREATE_CMD+=(--env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID")
fi
if [ -n "${AWS_DEFAULT_REGION:-}" ]; then
  CREATE_CMD+=(--env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION")
fi
if [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  CREATE_CMD+=(--env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY")
fi
if [ -n "${S3_BUCKET:-}" ]; then
  CREATE_CMD+=(--env "S3_BUCKET=$S3_BUCKET")
fi
if [ -n "${S3_PREFIX:-}" ]; then
  CREATE_CMD+=(--env "S3_PREFIX=$S3_PREFIX")
fi
if [ -n "${S3_ENDPOINT_URL:-}" ]; then
  CREATE_CMD+=(--env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL")
fi

if [ -n "${PDB_CACHE_DIR:-}" ]; then
  CREATE_CMD+=(--env "PDB_CACHE_DIR=$PDB_CACHE_DIR")
fi

if [ -n "${OPENMM_PLATFORM:-}" ]; then
  CREATE_CMD+=(--env "OPENMM_PLATFORM=$OPENMM_PLATFORM")
fi
if [ -n "${OPENMM_PRECISION:-}" ]; then
  CREATE_CMD+=(--env "OPENMM_PRECISION=$OPENMM_PRECISION")
fi
if [ -n "${OPENMM_DEVICE_INDEX:-}" ]; then
  CREATE_CMD+=(--env "OPENMM_DEVICE_INDEX=$OPENMM_DEVICE_INDEX")
fi

if [ -n "$JOB_PLATFORM" ]; then
  CREATE_CMD+=(--platform "$JOB_PLATFORM")
fi

if [ -n "$SUBNET_ID" ]; then
  CREATE_CMD+=(--subnet-id "$SUBNET_ID")
fi

"${CREATE_CMD[@]}"
