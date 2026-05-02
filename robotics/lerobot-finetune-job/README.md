---
title: Fine-tune a LeRobot Policy with Nebius AI Jobs
category: robotics
type: batch-job
runtime: nebius-ai-jobs
frameworks: [lerobot, pytorch, huggingface]
keywords: [robotics, fine-tuning, act-policy, diffusion-policy, serverless-jobs, s3]
difficulty: intermediate
---

# Fine-tune a LeRobot Policy on Nebius AI Jobs

Fine-tune a [LeRobot](https://github.com/huggingface/lerobot) ACT or Diffusion policy on a robotics dataset — no physical robot or local GPU required. The job provisions a GPU, downloads the dataset from HuggingFace Hub, trains the policy, saves the checkpoint to S3, and terminates.

| Section | What you get | Typical time |
| --- | --- | --- |
| [Quick start](#-30-second-quick-start) | One `job create` on GPU (no S3 persistence) | ~2 min |
| [Step 1 — Local smoke test](#step-1--try-it-locally-first-optional-but-recommended) | Same image, CPU-only, 50 steps (default) | ~2–5 min |
| [Step 2 — Object storage](#step-2--set-up-object-storage) | Bucket + credentials + env vars | ~10–15 min first time |
| [Step 3 — GPU job with S3](#step-3--launch-a-gpu-training-job) | Train and persist checkpoint | 20–60 min (5 000 steps) |
| [Step 4 — Get checkpoint](#step-4--retrieve-the-checkpoint) | Download and inspect results | ~2 min |
| [Project layout](#project-layout) | Where code, configs, and scripts live | ~1 min read |
| [Adapting](#adapting-to-your-own-use-case) | Change dataset, policy, or step count | — |
| [Troubleshooting](#troubleshooting) | Common failures and fixes | — |

---

## ⚡ 30-second quick start

```bash
nebius ai job create \
  --name "lerobot-act-pusht" \
  --image "mnrozhkov/lerobot-finetune:v0.0.1" \
  --platform "gpu-h100-sxm" \
  --preset "1gpu-16vcpu-200gb" \
  --timeout "6h" \
  --args "--policy act --dataset lerobot/pusht --steps 5000"
```

This trains without persisting the checkpoint (the VM is removed on completion). For **saving the checkpoint to your bucket**, add the `--env` lines from [Step 3](#step-3--launch-a-gpu-training-job).

> **Multiple subnets?** If the CLI asks you to pick a subnet, export `SUBNET_ID` and append `--subnet-id "$SUBNET_ID"` to the command.

---

## What this example does

```
Inside the container (LeRobot + PyTorch)
─────────────────────────────────────────
Download dataset from HuggingFace Hub (lerobot/pusht)
        ↓
Build ACT policy from scratch
        ↓
Offline training loop: N gradient steps on GPU
        ↓
Save HF-compatible checkpoint → outputs/train/<run-id>/
        ↓
Upload checkpoint to S3 bucket
```

**Use this example to:**
- Learn the Nebius AI Jobs submission pattern for ML training workloads
- Run a reproducible LeRobot fine-tune without managing GPU infrastructure
- Produce a portable, HF-compatible checkpoint you can evaluate or deploy

> **Not for:** production-quality policies. 5 000 steps is a validation run. For results comparable to the LeRobot paper, use 50 000–100 000 steps.

---

## Prerequisites

Install the [Nebius AI Cloud CLI](https://docs.nebius.com/cli/install) and [configure it](https://docs.nebius.com/cli/configure).

| Requirement | Why you need it |
| --- | --- |
| Nebius CLI (authenticated) | Submit and monitor jobs |
| Nebius Object Storage bucket | Persist the checkpoint (see setup below) |
| Docker (optional) | Local smoke test before using cloud credits |
| HuggingFace account (optional) | Required only for private datasets — `lerobot/pusht` is public |
| Subnet ID (sometimes) | Only if your project has **multiple subnets** |

### Local dev loop (optional)

```bash
cd robotics/lerobot-finetune-job
uv sync --group dev # creates .venv and installs deps (runtime + dev)
source .venv/bin/activate
pre-commit install # optional: ruff lint/format on commit
ruff check .
python -m train.run --help
```

---

## Step 1 — Try it locally first (optional but recommended)

Validate the container on your laptop before spending cloud credits.

`scripts/run_docker.sh` mounts **`train/`**, **`configs/`**, and **`lerobot-outputs/`** from this folder into the container. You can edit `train/run.py` on the host and re-run **without** rebuilding (`SKIP_BUILD=1`).

**Build and run:**

```bash
bash scripts/run_docker.sh
```

After the first successful build, iterate faster:

```bash
SKIP_BUILD=1 bash scripts/run_docker.sh
```

To open a shell in the same environment (optional), use the same image and volume flags as `run_docker.sh`, then run `python -m train.run …` or `lerobot-train --help` by hand.

Checkpoints from local runs appear under **`./lerobot-outputs/`** on the host (no S3 needed).

Or manually (same mounts as the script):

```bash
docker build --platform linux/amd64 -t lerobot-finetune:dev .

mkdir -p lerobot-outputs
docker run --rm --platform linux/amd64 \
  -v "$(pwd)/train:/lerobot/train" \
  -v "$(pwd)/configs:/lerobot/configs" \
  -v "$(pwd)/lerobot-outputs:/lerobot/outputs" \
  lerobot-finetune:dev \
  --policy act --dataset lerobot/pusht --steps 50
```

**Expected output:**

```
============================================================
LeRobot Fine-tuning Job
  Policy:   act
  Dataset:  lerobot/pusht
  Steps:    50
============================================================

Running: .../lerobot-train --policy.type=act --policy.push_to_hub=false ...

Downloading dataset: lerobot/pusht
Using device: cpu
...
S3 upload skipped — missing env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

> **macOS note:** Docker on macOS cannot use NVIDIA GPUs. `Using device: cpu` is expected here — the cloud job will use CUDA. The default 50-step smoke test on CPU usually finishes in a few minutes.

---

## Step 2 — Set up object storage

Results are written to S3-compatible storage. Pick one of two setups:

**A) Use the toolkit (recommended)**

```bash
COOKBOOK_ENV_FILE=.env.lerobot bash ../../scripts/bootstrap-env.sh                   # fills PROJECT_ID/SUBNET_ID
COOKBOOK_ENV_FILE=.env.lerobot bash ../../scripts/bootstrap-storage.sh lerobot lerobot-finetune-policy  # bucket prefix + object prefix
COOKBOOK_ENV_FILE=.env.lerobot source ../../scripts/activate.sh                      # load that .env into your shell
```

- Pass a name prefix (here `lerobot`) to get a unique bucket like `lerobot-<rand>`.
- Pass an object prefix (here `lerobot-finetune-policy`) to keep artifacts under that path.
- `.env` ends up with `S3_BUCKET`, `S3_PREFIX`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY`, and will reuse the same bucket on reruns.

**B) Manual setup**

Follow the [Nebius Object Storage quickstart](https://docs.nebius.com/object-storage/quickstart#configure-access-credentials-and-aws-cli-settings) to create a bucket and access keys, then export:

```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="lerobot-<your-suffix>"
export S3_PREFIX="lerobot-finetune-policy"
```

**Verify access:**

```bash
aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT_URL"
```

If the bucket is empty, the command prints nothing (exit 0). 

---

## Step 3 — Launch a GPU training job

```bash
nebius ai job create \
  --name "lerobot-act-pusht-5k" \
  --image "mnrozhkov/lerobot-finetune:v0.0.1" \
  --platform "gpu-h100-sxm" \
  --preset "1gpu-16vcpu-200gb" \
  --timeout "6h" \
  --disk-size 450Gi \
  --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" \
  --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" \
  --env "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" \
  --env "S3_BUCKET=$S3_BUCKET" \
  --env "S3_PREFIX=$S3_PREFIX" \
  --env "S3_ENDPOINT_URL=$S3_ENDPOINT_URL" \
  --args "--policy act --dataset lerobot/pusht --steps 5000"
```

> **Multiple VPC subnets:** If your tenancy has more than one subnet, add `--subnet-id "subnet-xxxxxxxx"` to the command. With a single subnet, omit this flag.

Or use the helper script, which validates env vars and builds the command for you:

```bash
bash scripts/run_serverless.sh act lerobot/pusht 5000
```

Copy the returned job ID, then follow logs live:

```bash
nebius ai logs <job-id> --follow
```

**Healthy run looks like:**

```
============================================================
LeRobot Fine-tuning Job
  Policy:   act
  Dataset:  lerobot/pusht
  Steps:    5000
============================================================

Downloading dataset: lerobot/pusht (206 episodes, 25 650 frames)
Using device: cuda                         ← GPU confirmed
step:  100 loss: 0.0912 grad_norm: 2.841
step:  200 loss: 0.0847 grad_norm: 2.603
...
step: 5000 loss: 0.0234 grad_norm: 0.847

Uploading 12 files to s3://lerobot-checkpoints/lerobot/lerobot-act-pusht-20240501T120000/
  config.json
  model.safetensors
  ...
Checkpoint saved to s3://lerobot-checkpoints/lerobot/lerobot-act-pusht-20240501T120000/
```

---

## Step 4 — Retrieve the checkpoint

List completed runs:

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/"
```

Download a checkpoint:

```bash
export RUN_ID="lerobot-act-pusht-20240501T120000"

aws s3 sync \
  "s3://$S3_BUCKET/$S3_PREFIX/$RUN_ID/" \
  "./$RUN_ID/"
```

Add `--endpoint-url "$S3_ENDPOINT_URL"` only if your AWS CLI is not configured for Nebius Object Storage.

**What you will find:**

```
lerobot-act-pusht-20240501T120000/
├── config.json              ← policy architecture and hyperparameters
├── model.safetensors        ← policy weights
├── preprocessor_config.json ← input normalisation config
└── train_config.json        ← full training run config for reproducibility
```

**Load and evaluate the checkpoint:**

```python
from lerobot.policies.act.modeling_act import ACTPolicy

policy = ACTPolicy.from_pretrained("./lerobot-act-pusht-20240501T120000/")
policy.eval()
```

Or push directly to the HuggingFace Hub:

```python
policy.push_to_hub("your-username/act-pusht-nebius")
```

---

## Project layout

```
.
├── Dockerfile          CUDA runtime + uv + LeRobot + boto3
├── train/              Entrypoint package
│   └── run.py          Arg parsing → lerobot-train → optional S3 upload
├── configs/
│   └── act_pusht.yaml  Reference training configuration (documented parameters)
├── lerobot-outputs/    Created locally; checkpoints when using mounted runs
└── scripts/
    ├── run_docker.sh      Build (optional) + run with host mounts for train/configs
    └── run_serverless.sh  Validate env vars and submit Nebius AI Job
```

---

## Adapting to your own use case

<details>
<summary>Train Diffusion Policy instead of ACT</summary>

```bash
nebius ai job create ... \
  --args "--policy diffusion --dataset lerobot/pusht --steps 5000"
```

Diffusion Policy typically needs more steps than ACT to reach comparable performance and is slower to train per step. Consider 50 000+ steps for meaningful results.

</details>

<details>
<summary>Use a different dataset (e.g. ALOHA simulation)</summary>

```bash
nebius ai job create ... \
  --args "--policy act --dataset lerobot/aloha_sim_insertion_scripted --steps 10000"
```

ALOHA datasets are larger — allocate more disk (`--disk-size 300Gi`) and more steps.

</details>

<details>
<summary>Fine-tune from an existing checkpoint</summary>

Upload a pretrained checkpoint to S3 (or use a HuggingFace Hub repo), then pass it via `--config-path`:

```bash
nebius ai job create ... \
  --args "--policy act --dataset lerobot/pusht --steps 2000 \
          --config-path lerobot/act_pusht"
```

`--config-path` accepts a local directory or a HuggingFace repo ID containing a `train_config.json`.

</details>

<details>
<summary>Enable evaluation during training</summary>

Add `--env pusht` and `--eval-episodes 10` to run environment rollouts every `save_freq` steps:

```bash
nebius ai job create ... \
  --args "--policy act --dataset lerobot/pusht --steps 5000 \
          --env pusht --eval-episodes 10"
```

Evaluation renders the gym environment. The container does not have a display server — add `apt-get install xvfb` to the Dockerfile and prepend the training command with `xvfb-run -a` if you encounter rendering errors.

</details>

<details>
<summary>Build and push to Docker Hub</summary>

Image repository name for this example is **`lerobot-finetune`**. Set **`REGISTRY`** (Docker Hub user or org) and **`IMAGE_TAG`**; the full name is `"${REGISTRY}/lerobot-finetune:${IMAGE_TAG}"`.

Example values (maintainer): **`REGISTRY=mnrozhkov`**, **`IMAGE_TAG=v0.0.1`**.

```bash
docker login   # once per machine — Docker Hub credentials

export REGISTRY="mnrozhkov"
export IMAGE_TAG="v0.0.1"
export IMAGE="${REGISTRY}/lerobot-finetune:${IMAGE_TAG}"

docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"
```


Use `"$IMAGE"` with `nebius ai job create --image "$IMAGE"`, or export `REGISTRY` / `IMAGE_TAG` / `IMAGE` before `scripts/run_serverless.sh`.

</details>

<details>
<summary>Log to Weights & Biases</summary>

```bash
nebius ai job create ... \
  --env "WANDB_API_KEY=$WANDB_API_KEY" \
  --args "--policy act --dataset lerobot/pusht --steps 5000 --wandb-enable true"
```

Expose `--wandb-enable` in `train/run.py` and pass `--wandb.enable=true` to the LeRobot subprocess, or set it in `configs/act_pusht.yaml`.

</details>

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Using device: cpu` in cloud logs | Check `--platform gpu-h100-sxm` and `--preset 1gpu-16vcpu-200gb` are set |
| `ModuleNotFoundError: lerobot` | Image not built correctly — rebuild with `docker build --no-cache` |
| `policy.repo_id` missing / push to hub | v0.5.1 may default `push_to_hub=True`; `train/run.py` passes `--policy.push_to_hub=false`. To push, set `--policy.push_to_hub=true` and supply `--policy.repo_id=your-org/your-model` |
| `FileExistsError` on `output_dir` | Remove the directory, use a new `--output-dir`, or omit it so a timestamped path is used |
| Dataset download fails / hangs | Nebius jobs have limited external network access by default; check the [Nebius docs](https://docs.nebius.com/serverless) for egress settings |
| Job completes but no S3 results | Check all `AWS_*` and `S3_*` env vars are set and the bucket exists |
| Unrecognised `--training.*` flags | In v0.5.1 use top-level `--steps` and `--batch_size` (see `lerobot-train --help`) |
| `multiple subnets found` on submission | Export `SUBNET_ID`, then add `--subnet-id "$SUBNET_ID"` to `job create` |
| OOM on L40S | Reduce `--batch-size` to 4 or switch to `--platform gpu-h100-sxm` |
