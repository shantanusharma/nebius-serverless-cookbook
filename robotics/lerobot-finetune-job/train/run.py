"""Fine-tune a LeRobot policy and upload the checkpoint to S3.

Entry point for the containerised training job:
  python -m train.run --policy act --dataset lerobot/pusht --steps 5000
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import boto3
    from botocore.config import Config as BotoConfig

    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune a LeRobot policy (ACT or Diffusion) and persist the checkpoint to S3.",
    )
    parser.add_argument(
        "--policy",
        default="act",
        choices=["act", "diffusion"],
        help="Policy architecture (default: act)",
    )
    parser.add_argument(
        "--dataset",
        default="lerobot/pusht",
        help="HuggingFace dataset repo_id (default: lerobot/pusht)",
    )
    parser.add_argument(
        "--env",
        default=None,
        help=(
            "Environment type for in-training evaluation, e.g. 'pusht'. "
            "Omit (or leave empty) to skip evaluation and reduce job time."
        ),
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=5000,
        help="Number of offline training steps (default: 5000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Training batch size per GPU (default: 8). Increase on H100 (try 32–64).",
    )
    parser.add_argument(
        "--eval-episodes",
        type=int,
        default=0,
        help=(
            "Episodes evaluated at each checkpoint (default: 0 = disabled). "
            "Requires --env to be set."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Local checkpoint output directory. Auto-generated with timestamp if omitted.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Training subprocess
# ---------------------------------------------------------------------------


def _build_train_cmd(args: argparse.Namespace, output_dir: Path) -> list[str]:
    """Build the LeRobot training command.

    In lerobot v0.5.1 the training entry point is the `lerobot-train` binary
    (registered as lerobot.scripts.lerobot_train:main). The older module path
    `lerobot.scripts.train` no longer exists in this release.
    """
    venv_bin = Path(sys.executable).parent
    # Primary: `lerobot-train` binary registered by pip/uv (v0.5.1+)
    lerobot_train = venv_bin / "lerobot-train"
    if lerobot_train.is_file():
        base: list[str] = [str(lerobot_train)]
    else:
        # Fallback: invoke as a module (older installs or editable source installs)
        import importlib.util

        module = (
            "lerobot.scripts.lerobot_train"
            if importlib.util.find_spec("lerobot.scripts.lerobot_train") is not None
            else "lerobot.scripts.train"
        )
        base = [sys.executable, "-m", module]

    # v0.5.1 top-level flags (confirmed via `lerobot-train --help`):
    #   --steps int, --batch_size int, --save_freq int, --num_workers int
    flags: list[str] = [
        f"--policy.type={args.policy}",
        # v0.5.1 defaults push_to_hub=True; without policy.repo_id validation fails.
        # Use lowercase false (draccus bool parsing). See huggingface/lerobot#1641.
        "--policy.push_to_hub=false",
        f"--dataset.repo_id={args.dataset}",
        f"--steps={args.steps}",
        f"--batch_size={args.batch_size}",
        f"--output_dir={output_dir}",
        "--wandb.enable=false",
    ]
    if args.env:
        flags.append(f"--env.type={args.env}")
    if args.eval_episodes > 0 and args.env:
        flags.append(f"--eval.n_episodes={args.eval_episodes}")
    return base + flags


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------


def _make_s3_client() -> object | None:
    if not _BOTO3_AVAILABLE:
        print("boto3 not installed — S3 upload skipped.")
        return None
    missing = [v for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY") if not os.environ.get(v)]
    if missing:
        print(f"S3 upload skipped — missing env vars: {', '.join(missing)}")
        return None
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-north1")
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=region,
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        config=BotoConfig(region_name=region),
    )


def _upload_checkpoint(output_dir: Path) -> bool:
    """Recursively upload *output_dir* to S3. Returns True on success."""
    client = _make_s3_client()
    if client is None:
        return False

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("S3_BUCKET not set — skipping upload.")
        return False

    prefix = os.environ.get("S3_PREFIX", "lerobot").rstrip("/")

    try:
        client.head_bucket(Bucket=bucket)
    except Exception as exc:
        print(f"Cannot access bucket '{bucket}': {exc}")
        return False

    files = [p for p in output_dir.rglob("*") if p.is_file()]
    print(f"\nUploading {len(files)} files to s3://{bucket}/{prefix}/{output_dir.name}/")
    for local_path in files:
        key = f"{prefix}/{output_dir.name}/{local_path.relative_to(output_dir).as_posix()}"
        client.upload_file(str(local_path), bucket, key)
        print(f"  {local_path.relative_to(output_dir)}")

    s3_path = f"s3://{bucket}/{prefix}/{output_dir.name}/"
    print(f"\nCheckpoint saved to {s3_path}")
    print(f'Download: aws s3 sync "{s3_path}" "./{output_dir.name}/"')
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()

    # Forward HuggingFace token so datasets/models can be fetched from the Hub.
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

    run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    dataset_slug = args.dataset.split("/")[-1]
    run_name = f"lerobot-{args.policy}-{dataset_slug}-{run_id}"
    output_dir = Path(args.output_dir or f"outputs/train/{run_name}")
    # Do NOT pre-create the directory: lerobot-train creates it itself and raises
    # FileExistsError if it already exists (resume=False). Let lerobot own creation.

    cmd = _build_train_cmd(args, output_dir)

    print("=" * 60)
    print("LeRobot Fine-tuning Job")
    print(f"  Policy:   {args.policy}")
    print(f"  Dataset:  {args.dataset}")
    print(f"  Steps:    {args.steps}")
    print(f"  Output:   {output_dir}")
    print("=" * 60)
    print(f"\nRunning: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, check=False)

    if result.returncode != 0:
        print(
            f"\nTraining exited with code {result.returncode}. Attempting checkpoint upload anyway.",
            file=sys.stderr,
        )

    _upload_checkpoint(output_dir)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
