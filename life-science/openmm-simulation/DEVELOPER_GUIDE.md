---
title: OpenMM serverless example — developer guide
category: life-sciences
type: developer-guide
runtime: nebius-ai-jobs
frameworks: [openmm, python]
keywords: [molecular-simulation, serverless-jobs, s3, cuda]
difficulty: intermediate
---

<!-- markdownlint-disable MD025 -->

# Developer guide — OpenMM + Nebius AI Jobs

This document is for **contributors and integrators**: Python environment, **scripts in `scripts/`**, storage configuration, and customization. The **step-by-step tutorial** for new users is [**README.md**](README.md).

## Contents

- [Audience and expectations](#audience-and-expectations)
- [Project layout](#project-layout)
- [1. Validate local setup](#1-validate-local-setup)
- [2. Start with the pre-built container](#2-start-with-the-pre-built-container)
- [3. Run your first Serverless job](#3-run-your-first-serverless-job)
- [4. Add S3-backed persistence](#4-add-s3-backed-persistence)
- [5. Run additional simulations](#5-run-additional-simulations)
- [How to adapt](#how-to-adapt)
- [Troubleshooting](#troubleshooting)

## Audience and expectations

This example runs a short OpenMM MD simulation from a PDB, then can write trajectory, logs, metadata, and plots to **S3-compatible** object storage. It is **not** a production MD protocol without your own validation.

**Typical profile:**

- **Compute:** `gpu-l40s-a`, preset `1gpu-8vcpu-32gb` (defaults inside `scripts/run_serverless.sh`; overridable via env vars)
- **Outputs:** processed PDB, `.dcd` trajectory, log, metadata, plots under `s3://$S3_BUCKET/$S3_PREFIX/<run-id>/` when S3 env vars are set on the job
- **Stack:** OpenMM `8.4.*` in the published image; **CUDA** in cloud; **CPU** in local Docker (especially on macOS)

**Prerequisites:**

- Nebius CLI installed and authenticated
- Python **3.11+** locally (for `sim` and scripts that use `uv`)
- Docker locally (optional but recommended for container checks)
- Nebius Object Storage for **persistent** cloud runs

## Project layout

| Path | Role |
| --- | --- |
| `sim/` | Simulation driver, metadata, S3 upload |
| `scripts/setup.sh` | Creates `.venv` via `uv` and runs `uv pip install .` |
| `scripts/run_docker.sh` | Local `docker run` with S3 env vars forwarded |
| `scripts/run_serverless.sh` | Builds and runs `nebius ai job create` with env forwarding |
| `assets/pdb/` | Bundled PDB fallback |
| `app/` | Optional Streamlit UI — [app/README.md](app/README.md) |
| `results/` | Local downloads / local runs |

---

## 1. Validate local setup

**Goal:** Confirm the Python package and `sim.run` entrypoint before containers or jobs.

### Recommended: setup script

From the example root (`life-science/openmm-simulation/`):

```bash
bash ./scripts/setup.sh
source .venv/bin/activate
```

`setup.sh` installs `uv` if needed, creates `.venv`, and installs the project with `uv pip install .`.

### Equivalent (manual)

```bash
uv venv --python python3
source .venv/bin/activate
uv pip install .
```

### Quick local smoke test

```bash
python -m sim.run --protein-id 1UBQ --steps 200
```

A bundled PDB (`assets/pdb/1UBQ.pdb`) supports offline-first runs. A successful run produces local artifacts (structures, short trajectory, logs, metadata). This validates **CPU-side** logic only; **GPU** behavior is checked on Nebius AI Jobs.

---

## 2. Start with the pre-built container

**Goal:** Validate the same OCI image you use in the cloud.

### Smoke test (no S3)

No AWS/S3 variables required; outputs stay inside the container.

```bash
docker run --rm mnrozhkov/openmm-serverless:v0.1.5 \
  --protein-id 1UBQ --steps 200
```

> **Note:** Docker on macOS does not expose NVIDIA GPUs. Use cloud logs for CUDA confirmation.

### S3-backed local run (script)

**Preferred** once Step 4 exports are in your shell: the script checks variables, pulls the image if needed, and forwards env into the container.

```bash
bash ./scripts/run_docker.sh 1UBQ 200
```

- **Default:** exits if `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `S3_BUCKET`, `S3_PREFIX`, or `S3_ENDPOINT_URL` is missing.
- **`--debug` (diagnostic only):** warns but continues (upload may fail or be incomplete). Do not use this mode for researcher-facing "golden path" runs.

```bash
bash ./scripts/run_docker.sh --debug 1UBQ 200
```

**Image overrides:** set `IMAGE` to a full image reference, or set `CONTAINER_REGISTRY_PATH` and `IMAGE_TAG` so the image is `"$CONTAINER_REGISTRY_PATH/openmm-serverless:$IMAGE_TAG"`.

### Equivalent (manual `docker run` with S3)

```bash
docker run --rm \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  -e S3_BUCKET="$S3_BUCKET" \
  -e S3_PREFIX="$S3_PREFIX" \
  -e S3_ENDPOINT_URL="$S3_ENDPOINT_URL" \
  "mnrozhkov/openmm-serverless:v0.1.5" --protein-id 1UBQ --steps 200
```

---

## 3. Run your first Serverless job

**Goal:** End-to-end job on Nebius AI Jobs **without** S3 (ephemeral disk only).

### Script (debug — diagnostic only, no strict S3)

```bash
bash ./scripts/run_serverless.sh --debug 1UBQ 200
```

In `--debug`, missing S3/AWS env vars are warnings; results may be **lost** when the job completes. Use it only for troubleshooting.

### Equivalent (manual minimal job)

```bash
nebius ai job create \
  --name "quick-serverless-openmm" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --timeout "1h" \
  --args "--protein-id 1UBQ --steps 200"
```

If your project has **multiple subnets**, add `--subnet-id "$SUBNET_ID"` (or set `SUBNET_ID` when using `run_serverless.sh` — the script appends it when non-empty).

```bash
nebius ai logs <job-id> --follow
```

### Verify GPU usage

In logs, expect OpenMM on **CUDA** in the cloud (wording may vary slightly, e.g. `OpenMM platform detected: CUDA`).

**Diagnostic job** (`openmm.testInstallation`):

```bash
nebius ai job create \
  --name "openmm-test-installation" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --timeout "1h" \
  --entrypoint "python" \
  --args "-m openmm.testInstallation"
```

---

## 4. Add S3-backed persistence

**Goal:** Persist outputs under `s3://$S3_BUCKET/$S3_PREFIX/`.

### 4.1 Configure Nebius Object Storage

Follow the [Nebius Object Storage quickstart](https://docs.nebius.com/object-storage/quickstart#configure-access-credentials-and-aws-cli-settings) for a bucket and keys. You should have `NB_ACCESS_KEY_AWS_ID` and `NB_SECRET_ACCESS_KEY`.

**Export** (adjust region/bucket names to your project):

```bash
export AWS_ACCESS_KEY_ID="$NB_ACCESS_KEY_AWS_ID"
export AWS_SECRET_ACCESS_KEY="$NB_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="openmm-simulation-s3"
export S3_PREFIX="openmm"
```

### 4.2 Validate S3 from your machine

After configuring the AWS CLI (optional; see quickstart), listing often works **without** `--endpoint-url`:

```bash
aws s3 ls "s3://$S3_BUCKET"
```

If your profile does not set the Nebius endpoint, use:

```bash
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "${S3_ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}"
```

Optional: persist credentials and endpoint in `aws configure` (same quickstart).

### 4.3 Validate S3 path in Docker (script)

```bash
bash ./scripts/run_docker.sh 1UBQ 200
```

### 4.4 Persistent Serverless job (script)

With all required exports present:

```bash
bash ./scripts/run_serverless.sh 1UBQ 1000
```

The script invokes `nebius ai job create` with:

- `--args "--protein-id <ID> --steps <N>"`
- `--format "jsonpath={.metadata.id}"`
- `--disk-size 450Gi`
- `--platform "$JOB_PLATFORM"` (default `gpu-l40s-a`)
- `--preset "$JOB_PRESET"` (default `1gpu-8vcpu-32gb`)
- `--timeout "$JOB_TIMEOUT"` (default `4h`)
- `--subnet-id "$SUBNET_ID"` when `SUBNET_ID` is set
- `--env` lines for each set `AWS_*` / `S3_*` variable (and optional `PDB_CACHE_DIR`, `OPENMM_*`)

### Equivalent (manual persistent job)

Same shape as [README.md](README.md) Step 3, for example:

```bash
nebius ai job create \
  --name "openmm-persistent-1ubq" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --timeout "4h" \
  --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" \
  --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" \
  --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" \
  --env "S3_BUCKET=$S3_BUCKET" \
  --env "S3_PREFIX=$S3_PREFIX" \
  --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL" \
  --args "--protein-id 1UBQ --steps 1000"
```

### List and download results

Prefixes:

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/"
```

Download one run:

```bash
aws s3 sync "s3://$S3_BUCKET/$S3_PREFIX/<run-id>/" "./results/<run-id>/"
```

Typical layout:

```text
<run-id>/
├── <protein>.pdb
├── <protein>_processed.pdb
├── <protein>_trajectory.dcd
├── <protein>_simulation.log
├── <protein>_metadata.txt
└── plots/
```

---

## 5. Run additional simulations

**Goal:** Same image; change protein and step count.

### Script

```bash
bash ./scripts/run_serverless.sh 2PTC 2000
bash ./scripts/run_serverless.sh 1CRN 5000
```

### Equivalent (manual)

```bash
nebius ai job create \
  --name "openmm-2ptc-2000" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --timeout "4h" \
  --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" \
  --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" \
  --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" \
  --env "S3_BUCKET=$S3_BUCKET" \
  --env "S3_PREFIX=$S3_PREFIX" \
  --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL" \
  --args "--protein-id 2PTC --steps 2000"
```

---

## How to adapt

### Environment variables for `run_serverless.sh`

| Variable | Default | Purpose |
| --- | --- | --- |
| `JOB_PLATFORM` | `gpu-l40s-a` | `--platform` |
| `JOB_PRESET` | `1gpu-8vcpu-32gb` | `--preset` |
| `JOB_TIMEOUT` | `4h` | `--timeout` |
| `SUBNET_ID` | (empty) | Adds `--subnet-id` when set |
| `IMAGE` | (from registry path or default image) | Full image reference |
| `IMAGE_TAG` | `v0.1.5` | With `CONTAINER_REGISTRY_PATH`, builds image name |
| `CONTAINER_REGISTRY_PATH` | (empty) | Prefix for `openmm-serverless:$IMAGE_TAG` |

Optional env forwarded to the container when set: `PDB_CACHE_DIR`, `OPENMM_PLATFORM`, `OPENMM_PRECISION`, `OPENMM_DEVICE_INDEX`.

### Use custom PDB cache

Default cache is `assets/pdb/`.

```bash
python -m sim.run --protein-id 1UBQ --steps 1000 --pdb-cache-dir /mnt/pdb-files
```

For jobs, pass in `--args` or set `PDB_CACHE_DIR` for `run_serverless.sh`.

### Build and push your own image

```bash
export IMAGE_TAG="<image-version>"
export CONTAINER_REGISTRY_PATH="<registry>/<namespace>"
docker build --platform linux/amd64 -t openmm-serverless:${IMAGE_TAG} .
docker tag openmm-serverless:${IMAGE_TAG} "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
docker push "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
```

Example (Docker Hub–style):

```bash
export IMAGE_TAG="v0.1.0"
export CONTAINER_REGISTRY_PATH="mnrozhkov"
docker build --platform linux/amd64 -t openmm-serverless:${IMAGE_TAG} .
docker tag openmm-serverless:${IMAGE_TAG} "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
docker push "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
```

`CONTAINER_REGISTRY_PATH` can target Docker Hub, Nebius Container Registry, or any OCI registry.

---

## Troubleshooting

### OpenMM import issues (local venv)

```bash
uv pip install --force-reinstall "openmm==8.4.0"
```

### S3 access or upload issues

```bash
aws s3 ls "s3://$S3_BUCKET"
aws configure list
```

If needed:

```bash
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "${S3_ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}"
```

### Job finishes but no results in S3

- Confirm `S3_BUCKET`, `S3_PREFIX`, and `S3_ENDPOINT_URL` are set **on the job** (`--env` or script forwarding).
- Confirm the service account can write to the bucket.
- Avoid `--debug` on `run_serverless.sh` when you require strict checks before submit.

### Invalid or missing PDB

```bash
python -m sim.run --protein-id 1UBQ --steps 200
```

Ensure custom PDBs exist under the configured cache path.

### GPU or preset issues

- Project has access to the selected `JOB_PLATFORM` / preset.
- Preset is available in your region.
- Quota is sufficient.

<!-- markdownlint-enable MD025 -->
