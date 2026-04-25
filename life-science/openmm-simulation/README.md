---
title: OpenMM Serverless Molecular Dynamics on Nebius AI Jobs
category: life-sciences
type: batch-job
runtime: nebius-ai-jobs
frameworks: [openmm, python]
keywords: [molecular-simulation, serverless-jobs, s3, cuda]
difficulty: beginner-friendly
---

# Molecular Dynamics in the Cloud with OpenMM + Nebius AI Jobs

Run a GPU-accelerated protein simulation in under 5 minutes — no local GPU, no environment setup, no CUDA drivers.

If this is your first run, use this exact path: **Step 2 (S3 setup) → Step 3 (launch) → Step 4 (download results)**.

For **local setup**, **helper scripts** (`scripts/setup.sh`, `run_docker.sh`, `run_serverless.sh`), and deeper customization, see **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**.

**How this doc is organized:** a **quick start** you can paste immediately, a short **what / why**, **prerequisites**, then **Steps 1–4** (local smoke test → S3 → GPU job → download results). After that: optional **local demos** (Streamlit + Docker), **more simulations**, **project layout**, **customization**, and **troubleshooting**.

| Section | What you get | Typical time |
| --- | --- | --- |
| [⚡ Quick start](#-30-second-quick-start) | One `job create` on GPU (no S3 persistence) | ~1 min |
| [Step 1 — Local smoke test](#step-1--try-it-locally-first-optional-but-recommended) | Same image as cloud, CPU-only | ~2–5 min |
| [Step 2 — Object storage](#step-2--set-up-object-storage) | Bucket + credentials + env vars | ~10–15 min first time |
| [Step 3 — GPU job with S3](#step-3--launch-a-gpu-job-with-persistence) | Persist logs, trajectory, plots | ~1–5 min compute |
| [Step 4 — Get results](#step-4--get-your-results) | List / sync run folder locally | ~2 min |
| [Local demos](#local-demos-optional) | Streamlit UI or Docker one-liner (optional) | ~2 min setup |
| [Run more simulations](#run-more-simulations) | Other proteins and step counts | — |
| [Project layout](#project-layout) | Where code, assets, and results live | ~1 min read |
| [Adapting to your use case](#adapting-to-your-own-use-case) | Custom PDB, own image, GPU sanity check | — |
| [Troubleshooting](#troubleshooting) | Common failures and fixes | — |

---

## ⚡ 30-second quick start

Pick a protein. Launch the job. Get results.

```bash
nebius ai job create \
  --name "my-first-md-job" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --args "--protein-id 1UBQ --steps 1000"
```

That's it. A GPU spins up and runs the simulation. No results stored (VM and boot disk removed on completion). For **writing results to your bucket**, add the `--env` lines from [Step 3](#step-3--launch-a-gpu-job-with-persistence).

> **Multiple subnets?** If the CLI says to pick a subnet, export `SUBNET_ID` and append `--subnet-id "$SUBNET_ID"` to the command, or use the local Streamlit dashboard (sidebar **Nebius job network**).

---

### What this example does

When you run **`nebius ai job create`** with `--image` and `--args`, Nebius AI Jobs starts a cloud worker, pulls your image, runs the container, and forwards your `--args` to the simulation command.

Everything below happens **inside the running container** — your laptop does not need OpenMM or CUDA installed.

```
Inside the container (OpenMM driver / sim package)
──────────────────────────────────────────────────
Resolve protein (e.g. 1UBQ) → load or fetch PDB
        ↓
Solvate → energy minimization
        ↓
AMBER ff14SB + TIP3P · NPT ensemble · 300 K
        ↓
Trajectory + logs + plots → S3 bucket
```

**Use this example to:**
- Validate a containerized OpenMM workflow on real GPU hardware
- Learn the Nebius AI Jobs submission pattern
- Build a reusable template for your own simulations

> **Not for:** production MD protocols. Timestep, box padding, and equilibration are set for quick validation. Adapt these for scientific use.

---

## Prerequisites

Install the [Nebius AI Cloud CLI](https://docs.nebius.com/cli/install) and [configure it](https://docs.nebius.com/cli/configure).

| Requirement | Why you need it |
|---|---|
| Nebius CLI (authenticated) | Submit and monitor jobs |
| Nebius Object Storage bucket | Persist results (see setup below) |
| Docker (optional) | Local smoke test before cloud run |
| Subnet ID (sometimes) | Only if your project has **multiple subnets** — same value as `--subnet-id` for `job create` |

---

## Step 1 — Try it locally first (optional but recommended)

Validate the container on your laptop before using cloud credits.

```bash
docker run --rm mnrozhkov/openmm-serverless:v0.1.5 \
  --protein-id 1UBQ --steps 200
```

You should see something like:

```
Loading PDB structure for 1UBQ...
Running force field: AMBER ff14SB + TIP3P water
Minimizing energy (1231 atoms)...
OpenMM platform detected: CPU
Starting NPT production run...
Step 200 | Temp: 300.1 K | E_pot: -45189.4 kJ/mol
Simulation complete.
```

> **macOS note:** Docker on macOS cannot use NVIDIA GPUs. `OpenMM platform: CPU` is expected here. The cloud job will use CUDA.

---

## Step 2 — Set up object storage

Results are written to S3-compatible storage. One-time setup.

**Create a bucket and credentials:**
Follow the [Nebius Object Storage quickstart](https://docs.nebius.com/object-storage/quickstart#configure-access-credentials-and-aws-cli-settings) to get:
- A bucket (e.g. `openmm-simulation-s3`)
- `NB_ACCESS_KEY_AWS_ID` and `NB_SECRET_ACCESS_KEY`

**Export these in your shell:**

```bash
export AWS_ACCESS_KEY_ID="$NB_ACCESS_KEY_AWS_ID"
export AWS_SECRET_ACCESS_KEY="$NB_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="openmm-simulation-s3"
export S3_PREFIX="openmm"
```

**Verify access:**

Use the same shell as the `export` block above, or run those exports again so `AWS_*` and `S3_BUCKET` are set. With credentials and region from Step 2 (and the [Nebius quickstart](https://docs.nebius.com/object-storage/quickstart#configure-access-credentials-and-aws-cli-settings) AWS config if you used it), listing usually works **without** `--endpoint-url`:

```bash
aws s3 ls "s3://$S3_BUCKET"
```

If your CLI is **not** configured for Nebius Object Storage and the command fails or hits the wrong endpoint, pass the URL explicitly (avoid an empty value: that triggers **`scheme is missing`**):

```bash
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "${S3_ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}"
```

Success check: the command prints your bucket contents (or no error if the bucket is empty).

---

## Step 3 — Launch a GPU job with persistence

```bash
nebius ai job create \
  --name "openmm-1ubq-1k" \
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

> **Multiple VPC subnets:** If your tenancy has more than one subnet (or the CLI asks you to choose), add **`--subnet-id "subnet-xxxxxxxx"`** to `job create` after **`--timeout`** (same line as the other flags). Use the subnet ID from the CLI prompt or your network setup. With a single subnet, or when the CLI does not require it, omit this flag.

Copy the returned job ID, then follow logs live:

```bash
nebius ai logs <job-id> --follow
```

**Healthy run looks like:**

```
Loading PDB structure for 1UBQ...
OpenMM platform detected: CUDA         ← GPU confirmed
Starting NPT production run...
Step 500  | Temp: 299.8 K | E_pot: -45201.3 kJ/mol
Step 1000 | Temp: 300.1 K | E_pot: -45198.7 kJ/mol
✓ Uploading to s3://openmm-simulation-s3/openmm/<run-id>/
✓ All artifacts saved successfully.
```

---

## Step 4 — Get your results

List completed runs:

Re-use the **Step 2** exports in this shell (or run that `export` block again in a new terminal).

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/"
```

Success check: you see one or more run folders (prefixes) under `s3://$S3_BUCKET/$S3_PREFIX/`.

If listing fails without an explicit endpoint, add  
`--endpoint-url "${S3_ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}"`  
(do not pass `--endpoint-url` when the variable is empty, or AWS CLI errors with **`scheme is missing`**).

Download a run:

```bash
aws s3 sync \
  "s3://$S3_BUCKET/$S3_PREFIX/<run-id>/" \
  "./results/<run-id>/"
```

Use the same `--endpoint-url "..."` suffix on `sync` only when you need it for your AWS CLI setup.

**What you'll find:**

```
<run-id>/
├── 1UBQ.pdb                  ← original input
├── 1UBQ_processed.pdb        ← solvated, minimized
├── 1UBQ_trajectory.dcd       ← full MD trajectory
├── 1UBQ_simulation.log       ← step-by-step energy & temperature
├── 1UBQ_metadata.txt         ← run parameters for reproducibility
└── plots/                    ← RMSD and energy plots
```

Open the trajectory in **VMD**, **PyMOL**, or **NGLview** (Jupyter):

```python
import nglview as nv, mdtraj as md
traj = md.load("results/<run-id>/1UBQ_trajectory.dcd",
               top="results/<run-id>/1UBQ_processed.pdb")
nv.show_mdtraj(traj)
```

---

## Run more simulations

Same image, different protein or step count — just change `--args`:

```bash
# Classic folding benchmark
nebius ai job create ... --args "--protein-id 1CRN --steps 5000"

# Protease–inhibitor complex
nebius ai job create ... --args "--protein-id 2PTC --steps 2000"

# Villin headpiece (ultra-fast folder)
nebius ai job create ... --args "--protein-id 1VII --steps 10000"
```

---

## Project layout

```
.
├── sim/              Python package: simulation, metadata, S3 upload
├── assets/pdb/       Bundled PDB files (offline fallback)
├── scripts/          Docker + job helpers — [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
└── results/          Local output directory (created at runtime)
```

---

## Adapting to your own use case

<details>
<summary>Use a custom PDB file</summary>

Copy your PDB to the container or point to a custom cache:

```bash
--args "--protein-id MY_PROTEIN --steps 1000 --pdb-cache-dir /mnt/pdb-files"
```

</details>

<details>
<summary>Build and push your own image</summary>

```bash
export IMAGE_TAG="v1.0.0"
export REGISTRY="your-dockerhub-user"

docker build --platform linux/amd64 -t openmm-serverless:${IMAGE_TAG} .
docker tag openmm-serverless:${IMAGE_TAG} ${REGISTRY}/openmm-serverless:${IMAGE_TAG}
docker push ${REGISTRY}/openmm-serverless:${IMAGE_TAG}
```

`REGISTRY` is agnostic — works with Docker Hub, Nebius Container Registry, or any OCI-compatible registry.

</details>

<details>
<summary>Verify GPU utilization explicitly</summary>

```bash
nebius ai job create \
  --name "openmm-gpu-check" \
  --image "mnrozhkov/openmm-serverless:v0.1.5" \
  --platform "gpu-l40s-a" \
  --preset "1gpu-8vcpu-32gb" \
  --entrypoint "python" \
  --args "-m openmm.testInstallation"
```

</details>

---

## Demos and scripts (optional)

Use these after you are comfortable with the steps above — lab meetings, onboarding, or day-to-day runs without re-reading the CLI flow.

| Aid | Run | Best for |
| --- | --- | --- |
| **Streamlit dashboard** | From the project root: `uv sync --group app`, then `cd app && uv run --group app streamlit run app.py` | Select protein → submit → monitor → plots from S3; reads the same env vars as the CLI |
| **Job / Docker scripts** | `bash ./scripts/run_serverless.sh …`, `bash ./scripts/run_docker.sh …` | Scripted submit and local S3 validation — [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) |

The Streamlit app uses a bright theme, **hot-reloads** when you edit `app.py` (see `app/.streamlit/config.toml`), and passes `--subnet-id` when `SUBNET_ID` is set. See [`app/README.md`](app/README.md) for a short UI tour.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `OpenMM platform: CPU` in cloud logs | Platform or preset not set correctly — check `--platform gpu-l40s-a` |
| Job completes but no S3 results | Check that all `AWS_*` and `S3_*` env vars are set and the bucket exists |
| `ImportError: openmm` locally | `uv pip install --force-reinstall "openmm==8.4.0"` |
| Job fails at PDB fetch | Start with the bundled `1UBQ` — it works offline |
| `multiple subnets found` / subnet error on submission | Export `SUBNET_ID`, then add `--subnet-id "$SUBNET_ID"` to `job create` (Streamlit sidebar: **Nebius job network**) |