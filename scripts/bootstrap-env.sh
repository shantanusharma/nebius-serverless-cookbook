#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# Ensure .env exists before any save_env calls.
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "${ROOT_DIR}/.env.example" ]]; then
    cp "${ROOT_DIR}/.env.example" "$ENV_FILE"
    echo "Created $ENV_FILE from .env.example"
  else
    touch "$ENV_FILE"
    echo "Created empty $ENV_FILE (fill required values as needed)"
  fi
fi

load_env

banner "Bootstrap environment (CLI + project/subnet)"

OS="$(uname -s)"

install_aws() {
  echo "  → Installing AWS CLI..."
  if [[ "$OS" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install awscli
    else
      curl -fsSL "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o /tmp/AWSCLIV2.pkg
      sudo installer -pkg /tmp/AWSCLIV2.pkg -target /
      rm /tmp/AWSCLIV2.pkg
    fi
  elif [[ "$OS" == "Linux" ]]; then
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
    unzip -q /tmp/awscliv2.zip -d /tmp/awscli-install
    sudo /tmp/awscli-install/aws/install --update
    rm -rf /tmp/awscliv2.zip /tmp/awscli-install
  else
    echo "  ✗ Unsupported OS for auto-install: $OS"
    echo "    Install manually: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
    exit 1
  fi
  echo "  ✓ aws installed: $(aws --version 2>&1)"
}

install_jq() {
  echo "  → Installing jq..."
  if [[ "$OS" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install jq
    else
      echo "  ✗ Homebrew not found. Install jq manually: https://jqlang.github.io/jq/"
      exit 1
    fi
  elif [[ "$OS" == "Linux" ]]; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y jq
    elif command -v yum >/dev/null 2>&1; then
      sudo yum install -y jq
    else
      JQ_URL="https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64"
      curl -fsSL "$JQ_URL" -o /usr/local/bin/jq
      chmod +x /usr/local/bin/jq
    fi
  fi
  echo "  ✓ jq installed: $(jq --version)"
}

install_curl() {
  echo "  → Installing curl..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install curl
  elif [[ "$OS" == "Linux" ]]; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y curl
    elif command -v yum >/dev/null 2>&1; then
      sudo yum install -y curl
    fi
  fi
  echo "  ✓ curl installed: $(curl --version | head -1)"
}

echo ""
echo "── Checking required CLIs ─────────────────────────────"

if ! command -v nebius >/dev/null 2>&1; then
  echo "  ✗ nebius CLI not found."
  echo "    Install from: https://docs.nebius.com/cli/install"
  echo "    Then run: nebius profile create"
  exit 1
fi
echo "  ✓ nebius: $(nebius version)"

if ! command -v aws >/dev/null 2>&1; then
  echo "  ✗ aws not found — auto-installing..."
  install_aws
fi
echo "  ✓ aws: $(aws --version 2>&1)"

if ! command -v jq >/dev/null 2>&1; then
  echo "  ✗ jq not found — auto-installing..."
  install_jq
fi
echo "  ✓ jq: $(jq --version)"

if ! command -v curl >/dev/null 2>&1; then
  echo "  ✗ curl not found — auto-installing..."
  install_curl
fi
echo "  ✓ curl: $(curl --version | head -1)"

NEBIUS_REGION="${NEBIUS_REGION:-eu-north1}"

echo ""
echo "── Resolving Nebius project ───────────────────────────"

if ! nebius config get parent-id >/dev/null 2>&1; then
  echo "  ✗ Nebius parent-id is not configured."
  echo "    Run: nebius profile create"
  echo "    Then: nebius config set parent-id <your_project_id>"
  exit 1
fi

PROJECT_ID="$(resolve_project_id)"
echo "  ✓ project_id: $PROJECT_ID"
save_env PROJECT_ID "$PROJECT_ID"

CLI_PARENT_ID="$(nebius config get parent-id 2>/dev/null || true)"
if [[ -n "$CLI_PARENT_ID" && "$CLI_PARENT_ID" != "$PROJECT_ID" ]]; then
  echo ""
  echo "  ⚠  Project mismatch:"
  echo "       .env PROJECT_ID              = $PROJECT_ID"
  echo "       Nebius CLI default parent-id = $CLI_PARENT_ID"
  echo "     Scripts use .env (so they're fine), but ad-hoc 'nebius ...' commands"
  echo "     in your terminal will target the CLI default. Align them with:"
  echo "       nebius config set parent-id $PROJECT_ID"
fi

echo ""
echo "── Resolving subnet ───────────────────────────────────"
SUBNET_ID="$(resolve_subnet_id)"
echo "  ✓ subnet_id: $SUBNET_ID"
save_env SUBNET_ID "$SUBNET_ID"

save_env NEBIUS_REGION "$NEBIUS_REGION"

echo ""
echo "── Configuring AWS CLI defaults ───────────────────────"
aws configure set region "$NEBIUS_REGION"
aws configure set output json
echo "  ✓ aws configured for region=$NEBIUS_REGION (credentials set in storage step)"

echo ""
echo "── Env bootstrap complete ✓ ───────────────────────────"
echo "Next: bash scripts/bootstrap-storage.sh"
