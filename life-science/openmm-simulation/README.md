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

This example runs a short OpenMM molecular dynamics simulation from a PDB structure, then writes trajectory, logs, metadata, and plots to object storage.

It is designed as a practical workflow example for running short MD jobs on Nebius AI Jobs, validating the container locally, and persisting outputs to object storage. It is **not** intended to be a production-ready or scientifically validated MD protocol without further adaptation.

## 📋 Table of Contents

- [🎯 What You'll Learn](#-what-youll-learn)
- [🚀 Prerequisites](#-prerequisites)
- [1. Validate local setup](#1-validate-local-setup)
- [2. Start with the pre-built container](#2-start-with-the-pre-built-container)
- [3. Run your first Serverless job](#3-run-your-first-serverless-job)
- [4. Add S3-backed persistence](#4-add-s3-backed-persistence)
- [5. Run additional simulations](#5-run-additional-simulations)
- [🧱 Project Structure](#-project-structure)
- [How to Adapt](#how-to-adapt)
- [🆘 Troubleshooting](#-troubleshooting)

---

## 🎯 What You'll Learn

This guide shows how to:

1. Validate the OpenMM environment with a short local smoke test.
2. Validate the container locally before using Serverless.
3. Run a GPU-backed molecular dynamics job with Nebius AI Jobs.
4. Persist simulation outputs to S3-compatible object storage.
5. Re-run the same container with different proteins or step counts.
6. Adapt the example for your own image, storage setup, or PDB cache.

## 🚀 Prerequisites

- Nebius CLI installed and authenticated
- Python `3.11+` installed locally
- Docker installed locally
- Access to Nebius Serverless Jobs

## Expected run profile

- Compute: `gpu-l40s-a`, preset `1gpu-8vcpu-32gb`
- Example output: processed PDB, trajectory, simulation log, metadata, plots
- Best for: validating containerized OpenMM workflows on Nebius AI Jobs
- CUDA stack in this example is pinned to OpenMM `8.4.*` + `cuda-version=12` for broad driver compatibility

For persistent runs, you will also need Nebius Object Storage (S3-compatible). This is covered in [How to Adapt: Configure Nebius Object Storage (S3)](#configure-nebius-object-storage-s3).

---

## 1. Validate local setup

**Goal:** Confirm that the Python environment and simulation entrypoint work before testing containers or Serverless Jobs.

### Setup local environment

```bash
uv venv --python python3
source .venv/bin/activate
uv pip install .
```

### Quick local smoke test

```bash
python -m sim.run --protein-id 1UBQ --steps 200
```

A bundled PDB file (`assets/pdb/1UBQ.pdb`) is included so the first run works offline.

A successful run should produce local simulation artifacts such as:

- processed structure files
- a short trajectory
- logs and metadata

The local smoke test is only for validating setup. The **Serverless job path** is the main GPU-backed workflow for this tutorial.

---

## 2. Start with the pre-built container

**Goal:** Use the fastest path first and validate the container locally before running on Serverless.

This tutorial uses a pre-built container image:

```bash
docker run --rm mnrozhkov/openmm-serverless:v0.1.5 --protein-id 1UBQ --steps 200
```

This image contains the OpenMM runtime and the example code used throughout the guide.

Running it locally in Docker is the fastest way to catch container or runtime issues before using Serverless.

At this stage:

- no S3 configuration is required
- outputs stay inside the container unless you explicitly mount storage
- this is meant only as a validation step

> **Note:** local Docker on macOS does not expose NVIDIA GPUs, so GPU utilization checks must be done on a Serverless GPU job.

Use this default path if you want to focus on the workflow first. If you prefer to inspect or customize the environment, you can build and push your own image later in [How to Adapt](#how-to-adapt).

<!-- markdownlint-disable MD033 -->
<details>
<summary>Optional: use the helper script instead</summary>

```bash
bash ./scripts/run_docker.sh 1UBQ 200
```

Use the direct `docker run` path to understand the workflow. Use the helper script if you want a shorter command.

</details>
<!-- markdownlint-enable MD033 -->

---

## 3. Run your first Serverless job

**Goal:** Validate the end-to-end Serverless flow with the minimum setup.

Start with a minimal job run:

```bash
nebius ai job create \
  --name "quick-serverless-openmm" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --timeout "1h" \
  --args "--protein-id 1UBQ --steps 200"
```

If your project has multiple subnets, append:

```bash
--subnet-id "$SUBNET_ID"
```

Copy the returned job ID and follow logs with:

```bash
nebius ai logs <job-id> --follow
```

This run validates that:

- the container starts correctly on Nebius AI Jobs
- the simulation executes on Serverless
- logs are available through the CLI

> **Important:** without S3 configuration, outputs are written only to ephemeral container disk and are deleted when the job completes.

### 3.1 Verify GPU usage

Check logs. Expected line for a healthy GPU run:

```text
Starting MD simulation for ...
Loading PDB structure...
Using OpenMM platform: CUDA
```

Optional deeper check (manual diagnostic job):

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

**Goal:** Persist simulation outputs and validate the full end-to-end flow.

### 4.1 Configure Nebius Object Storage

Export the environment variables described in [How to Adapt: Configure Nebius Object Storage (S3)](#configure-nebius-object-storage-s3).

At minimum, the example expects:

```bash
export AWS_ACCESS_KEY_ID="$NB_ACCESS_KEY_AWS_ID"
export AWS_SECRET_ACCESS_KEY="$NB_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="eu-north1" # change to region in your project
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="openmm-simulation-s3"
export S3_PREFIX="openmm"
```

### 4.2 Validate S3-backed execution in Docker first

Before using Serverless, test the upload path locally in Docker:

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

This is a faster way to validate:

- container runtime
- S3 credentials
- upload logic

before running a full Serverless job.

### 4.3 Run a persistent Serverless job

Once Docker + S3 works, run the full Serverless job:

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

Each run writes results under a unique prefix inside:

```text
s3://$S3_BUCKET/$S3_PREFIX/
```

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

A successful persistent run should produce:

- a processed PDB file
- a trajectory file (`.dcd`)
- a simulation log
- a metadata file
- optional plots

---

## 5. Run additional simulations

**Goal:** Reuse the same image and launch more jobs by changing input arguments.

Examples:

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
  --args "--protein-id 2PTC --steps 2000" # Change protein and steps here
```

<!-- markdownlint-disable MD033 -->
<details>
<summary>Optional: use the helper script for debug, strict, and repeated runs</summary>

Debug-mode smoke test (no S3 persistence required):

```bash
bash ./scripts/run_serverless.sh --debug 1UBQ 1000
```

In `--debug` mode:

- missing S3/AWS env vars produce warnings rather than hard failures
- results are written only to container boot disk
- container boot disk is ephemeral and is deleted when the job completes

Strict-mode persistent run (requires S3 env vars):

```bash
bash ./scripts/run_serverless.sh 1UBQ 1000
```

Run additional simulations with new args:

```bash
bash ./scripts/run_serverless.sh 1UBQ 1000
bash ./scripts/run_serverless.sh 2PTC 2000
bash ./scripts/run_serverless.sh 1CRN 5000
```

</details>
<!-- markdownlint-enable MD033 -->


---

## 🧱 Project Structure

- `scripts/` — runnable helper scripts for setup, Docker validation, and job submission
- `sim/` — Python modules for simulation, metadata, and S3 upload logic
- `assets/` — static files and bundled local PDB fallback cache
- `results/` - folder created during local/docker runs, contains simulation results

---

## How to Adapt

Use this section if you want to run with your own image repository (public or private) instead of the default public path.

### Configure Nebius Object Storage (S3)

1. Create a bucket, for example:

```text
openmm-simulation-s3
```

1. Create a service account and access key, and add the service account to the `editors` group.
   Follow: [Nebius Object Storage quickstart](https://docs.nebius.com/object-storage/quickstart#configure-access-credentials-and-aws-cli-settings)

At the end of this step, you should have:

- `NB_ACCESS_KEY_AWS_ID`
- `NB_SECRET_ACCESS_KEY`

1. Export the environment variables used by this example.

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

1. Validate access to the bucket.

```bash
aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID"
aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY"
aws configure set region "$AWS_DEFAULT_REGION"
aws configure set endpoint_url "$S3_ENDPOINT_URL"
aws s3 ls "s3://$S3_BUCKET"
```

### Use custom PDB cache location

By default, `sim.run` looks for PDB files in `assets/pdb/`.

To override the cache location explicitly:

```bash
python -m sim.run --protein-id 1UBQ --steps 1000 --pdb-cache-dir /mnt/pdb-files
```

### Use your docker image

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

`CONTAINER_REGISTRY_PATH` is registry-agnostic and can point to Docker Hub, Nebius Container Registry, or any other OCI-compatible registry.

---

## 🆘 Troubleshooting

### OpenMM import issues

```bash
uv pip install --force-reinstall "openmm==8.4.0"
```

### S3 access or upload issues

```bash
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT_URL"
aws configure list
```

### Job finishes but no results appear in S3

Check that:

- `S3_BUCKET`, `S3_PREFIX`, and `S3_ENDPOINT_URL` are set correctly
- the service account has bucket access
- you are not running in `--debug` mode

### Invalid or missing PDB input

Start with the bundled example:

```bash
python -m sim.run --protein-id 1UBQ --steps 200
```

If using custom structures, verify that the PDB file exists in the configured cache path.

### GPU or preset issues

If job submission fails, verify that:

- your project has access to the selected platform
- the selected preset is available in your region
- quota is sufficient for the requested resources
