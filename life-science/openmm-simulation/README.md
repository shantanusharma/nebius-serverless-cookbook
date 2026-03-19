---
title: OpenMM Serverless Molecular Dynamics with Nebius AI Jobs
category: life-sciences
type: batch-job
runtime: nebius-ai-jobs
frameworks: [openmm, python]
keywords: [molecular-simulation, serverless-jobs, s3, cuda]
difficulty: intermediate
---

<!-- markdownlint-disable MD025 -->
# OpenMM Serverless Molecular Dynamics with Nebius AI Jobs

Run GPU-accelerated molecular dynamics simulations with a CLI-first workflow.

This example is intentionally **CLI only**.  
No API server is included in this directory.

## 📋 Table of Contents

- [🎯 What You'll Learn](#-what-youll-learn)
- [🚀 Prerequisites](#-prerequisites)
- [1. Get started with OpenMM simulations](#1-get-started-with-openmm-simulations)
- [2. Use pre-built Docker image](#2-use-pre-built-docker-image)
- [3. Create and Run First Job](#3-create-and-run-first-job)
- [4. Run Additional Simulations (new args)](#4-run-additional-simulations-new-args)
- [5. Save and Explore Results in S3](#5-save-and-explore-results-in-s3)
- [🧱 Project Structure](#-project-structure)
- [How to Adapt](#how-to-adapt)
- [🆘 Troubleshooting](#-troubleshooting)

---

## 🎯 What You'll Learn

This guide walks through a complete Serverless v1 Jobs flow:

1. Use a pre-built Docker image (or build your own in [How to Adapt](#how-to-adapt)).
2. Configure and submit a simulation job with `nebius ai job create`.
3. Launch additional jobs by changing simulation arguments.
4. Store and inspect simulation outputs in S3-compatible object storage.

---

## 🚀 Prerequisites

- Nebius CLI installed and authenticated.
- Python `3.14` (required by this example).
- Docker installed locally.
- Access to Nebius Serverless Jobs.

For strict S3-backed runs, see [How to Adapt: Configure Nebius Object Storage (S3)](#configure-nebius-object-storage-s3).

---

## 1. Get started with OpenMM simulations

**Goal:** Validate local setup and run a quick simulation before submitting jobs.

### Setup local environment

```bash
uv venv --python python3.14
source .venv/bin/activate
uv pip install .
```

### Quick local smoke test

```bash
python -m sim.run --protein-id 1UBQ --steps 200
```

A bundled PDB file (`assets/pdb/1UBQ.pdb`) is included so the first run works offline.

---

## 2. Use pre-built Docker image

**Goal:** Keep the default path simple by using the pre-built image.

```bash
# Use pre-built image (default tutorial path)
export IMAGE="mnrozhkov/openmm-serverless:v0.1.1"
```

If you want to build and push your own image, see [How to Adapt](#how-to-adapt).

---

## 3. Create and Run First Job

**Goal:** Start with minimum setup in debug mode, then run strict S3-backed jobs.

### 3.1 Quick debug run (minimum setup)

Use debug mode to validate that serverless simulation runs end-to-end without setting S3 credentials.

```bash
bash ./scripts/run_serverless.sh --debug 1UBQ 1000
```

In `--debug` mode:

- missing S3/AWS env vars produce warnings, not hard failures
- results are written only to container boot disk
- boot disk is ephemeral in Serverless and is deleted when job completes, so outputs are not persisted

### 3.2 Proper run with S3 persistence (strict mode)

Set required environment variables using [How to setup S3](#configure-nebius-object-storage-s3).

Then run in default strict mode:

```bash
bash ./scripts/run_serverless.sh 1UBQ 1000
```

In strict mode, the script fails if required env vars are missing.

The helper script submits a job with `nebius ai job create`.

### Equivalent manual command (strict mode)

```bash
JOB_NAME="openmm-1ubq-1000-$(date +%Y%m%d%H%M%S)"

nebius ai job create \
  --name "$JOB_NAME" \
  --image "$IMAGE" \
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

If your project has multiple subnets, append this flag inside `nebius ai job create`:

```bash
--subnet-id "$SUBNET_ID"
```

---

## 4. Run Additional Simulations (new args)

**Goal:** Reuse the same image and launch more jobs by changing args.

```bash
bash ./scripts/run_serverless.sh 1UBQ 1000
bash ./scripts/run_serverless.sh 2PTC 2000
bash ./scripts/run_serverless.sh 1CRN 5000
```

---

## 5. Save and Explore Results in S3

Typical artifacts:

```text
<run-id>/
├── <protein>.pdb
├── <protein>_processed.pdb
├── <protein>_trajectory.dcd
├── <protein>_simulation.log
├── <protein>_metadata.txt
└── plots/
```

List result prefixes:

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/"
```

Download one run locally:

```bash
aws s3 sync "s3://$S3_BUCKET/$S3_PREFIX/<run-id>/" "./results/<run-id>/"
```

---

## 🧱 Project Structure

- `scripts/` - canonical runnable scripts (`setup.sh`, `run_serverless.sh`, `run_docker.sh`)
- `sim/` - simulation and storage Python modules
- `assets/` - static files and local PDB fallback cache

---

## How to Adapt

Use this section if you want to run with your own image repository (public or private) instead of the public happy path.

### Configure Nebius Object Storage (S3)

1. Create a bucket: `openmm-simulation-s3`.

2. Create a service account and access key, and add the service account to `editors` group.  
Follow: [Nebius Object Storage quickstart](https://docs.nebius.com/object-storage/quickstart#configure-access-credentials-and-aws-cli-settings)  

At the end of this step, you should have:

- `NB_ACCESS_KEY_AWS_ID`
- `NB_SECRET_ACCESS_KEY`

1. Export env vars used by this example.

<!-- markdownlint-disable MD033 -->
<details>
<summary>Copy/paste example (NB_* -> AWS_*)</summary>

```bash
export AWS_ACCESS_KEY_ID="$NB_ACCESS_KEY_AWS_ID"
export AWS_SECRET_ACCESS_KEY="$NB_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="eu-north1" # change to region of your project
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="openmm-simulation-s3"
export S3_PREFIX="openmm"
```

</details>
<!-- markdownlint-enable MD033 -->

1. Run AWS configuration and test bucket access.

```bash
aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID"
aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY"
aws configure set region "$AWS_DEFAULT_REGION"
aws configure set endpoint_url "$S3_ENDPOINT_URL"
aws s3 ls "s3://$S3_BUCKET"
```

### Custom PDB cache location

By default, `sim.run` looks for PDB files in `assets/pdb/`.  
To override (e.g. an S3-mounted volume inside a container), pass the path explicitly:

```bash
python -m sim.run --protein-id 1UBQ --steps 1000 --pdb-cache-dir /mnt/pdb-files
```

The `PDB_CACHE_DIR` environment variable is also supported as a fallback.

### Option: build and push your own image

```bash
export IMAGE_TAG="<image-version>"
export CONTAINER_REGISTRY_PATH="<registry>/<namespace>"
docker build --platform linux/amd64 -t openmm-serverless:${IMAGE_TAG} .
docker tag openmm-serverless:${IMAGE_TAG} "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
docker push "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
```

<!-- markdownlint-disable MD033 -->
<details>
<summary>Example: use my Docker Hub repo</summary>

```bash
export IMAGE_TAG="v0.1.0"
export CONTAINER_REGISTRY_PATH="mnrozhkov"
docker build --platform linux/amd64 -t openmm-serverless:${IMAGE_TAG} .
docker tag openmm-serverless:${IMAGE_TAG} "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
docker push "$CONTAINER_REGISTRY_PATH/openmm-serverless:${IMAGE_TAG}"
```

</details>
<!-- markdownlint-enable MD033 -->

`CONTAINER_REGISTRY_PATH` is registry-agnostic and can point to Docker Hub, Nebius Container Registry or any other OCI-compatible registry.

---

## 🆘 Troubleshooting

### OpenMM import issues

```bash
uv pip install --force-reinstall "openmm==8.4.0"
```

### S3 access/upload issues

```bash
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT_URL"
aws configure list
```
