#!/bin/bash

# Setup script for local development

set -e

echo "Setting up OpenMM Serverless Simulation environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "Please restart your shell or run: source ~/.bashrc (or ~/.zshrc)"
    echo "Then run this script again."
    exit 1
fi

if [ -n "${UV_PYTHON:-}" ]; then
    PYTHON_BIN="$UV_PYTHON"
else
    PYTHON_BIN=""
    for candidate in python3.14 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            CANDIDATE_VERSION="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            if [ "$CANDIDATE_VERSION" = "3.14" ]; then
                PYTHON_BIN="$candidate"
                break
            fi
        fi
    done
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Python 3.14 is required for this example." >&2
    echo "Install Python 3.14 and rerun ./scripts/setup.sh, or set UV_PYTHON=python3.14." >&2
    exit 1
fi

echo "Using Python interpreter: $PYTHON_BIN"
echo "Creating virtual environment..."
uv venv --clear --python "$PYTHON_BIN"

echo "Installing dependencies..."
uv pip install .

echo "Setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To run a local simulation:"
echo "  python -m sim.run --protein-id 1UBQ --steps 1000"
echo ""
echo "To submit a serverless job:"
echo "  bash ./scripts/run_serverless.sh 1UBQ 1000"
echo ""
