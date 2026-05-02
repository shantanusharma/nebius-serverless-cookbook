#!/usr/bin/env bash
set -euo pipefail

#!/usr/bin/env bash
set -euo pipefail

# Hardcoded smoke commands for quick local validation (CPU via Docker).
# Requires HF_TOKEN set for the gated dataset; otherwise those two commands will fail.
# Steps are fixed at 20.

echo "Running hardcoded smoke tests..."
echo ""

echo "==== act / lerobot/pusht ===="
BATCH_SIZE=4 SKIP_BUILD=1 bash scripts/run_docker.sh act lerobot/pusht 20
echo ""

echo "==== diffusion / lerobot/pusht ===="
BATCH_SIZE=4 SKIP_BUILD=1 bash scripts/run_docker.sh diffusion lerobot/pusht 20
echo ""

echo "==== act / lerobot/aloha_sim_transfer_cube_human ===="
HF_TOKEN="${HF_TOKEN:-}" NUM_WORKERS=0 BATCH_SIZE=2 SKIP_BUILD=1 \
  bash scripts/run_docker.sh act lerobot/aloha_sim_transfer_cube_human 20
echo ""

echo "==== diffusion / lerobot/aloha_sim_transfer_cube_human ===="
HF_TOKEN="${HF_TOKEN:-}" NUM_WORKERS=0 BATCH_SIZE=2 SKIP_BUILD=1 \
  bash scripts/run_docker.sh diffusion lerobot/aloha_sim_transfer_cube_human 20
echo ""

echo "✓ Done."
