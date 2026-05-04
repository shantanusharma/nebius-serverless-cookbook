# Scripts toolkit (optional)

Opt-in helpers for common setup across cookbook examples. Existing examples remain self-contained; use these scripts to avoid repeating project/subnet/bucket setup.

## Quick start

```bash
# Shared .env (default)
bash scripts/bootstrap-env.sh
bash scripts/bootstrap-storage.sh
source scripts/activate.sh

# Per-example .env (recommended when running multiple examples)
COOKBOOK_ENV_FILE=.env.lerobot bash scripts/bootstrap-env.sh
COOKBOOK_ENV_FILE=.env.lerobot bash scripts/bootstrap-storage.sh lerobot lerobot-finetune-policy
COOKBOOK_ENV_FILE=.env.lerobot source scripts/activate.sh
```

Then run any example README commands.

Prefer per-example env files to keep buckets/creds separate (`.env.<example>`). If you want to manage everything manually, skip the scripts and export the same variables in your shell (`PROJECT_ID`, `SUBNET_ID`, `S3_BUCKET`, `S3_PREFIX`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`).

## Helpers

- `lib.sh` — shared functions (env loading, save_env, resolve_project_id/subnet_id, resolve_resource_id, nebius_capture_json, banner)
- `bootstrap-env.sh` — verifies `nebius`/`aws`/`jq`/`curl`, resolves `PROJECT_ID`/`SUBNET_ID`, writes `.env`, configures AWS CLI region/output
- `bootstrap-storage.sh [bucket_prefix] [s3_prefix]` — creates/reuses bucket + service account, creates v2 access key, configures AWS CLI credentials, writes S3/AWS vars into `.env`
- `activate.sh` — source to load `.env` into the current shell for ad-hoc CLI calls
- `cleanup.sh` — deletes bucket + service account; optional `--job NAME` and `--endpoint NAME`; skip prompts with `ASSUME_YES=1` or `-y`

## Planned helpers (not in this repo yet)

- `submit-job.sh` — build a `nebius ai job create` command from `.env` (SUBNET_ID, BUCKET_ID, AWS_*, S3_*)
- `watch-job.sh` — poll job state and tail logs on failure
- `endpoint-wait.sh` — wait for endpoint RUNNING + public endpoint
- `endpoint-smoke.sh` — warmup-tolerant curl + retry for vLLM/OpenAI endpoints

Open a PR if you want these sooner. The lib primitives (`wait_endpoint_running`, `http_post_json_retry`, etc.) will ship with those helpers.
