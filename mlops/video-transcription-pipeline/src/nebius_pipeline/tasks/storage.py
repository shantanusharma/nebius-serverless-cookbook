"""S3-compatible storage tasks for Nebius Object Storage."""

import boto3
from botocore.exceptions import ClientError
from prefect import task
from prefect.logging import get_run_logger

from nebius_pipeline.config import settings


def get_s3_client():
    """Create a boto3 client configured for Nebius Object Storage."""
    return boto3.client(
        "s3",
        endpoint_url=settings.nebius_endpoint,
        region_name=settings.nebius_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _list_keys(prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = get_s3_client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.nebius_bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def _filename(key: str) -> str:
    return key.rsplit("/", 1)[-1]


@task(retries=2, retry_delay_seconds=5)
def object_exists(key: str) -> bool:
    """Return True when an object exists in the bucket."""
    try:
        get_s3_client().head_object(Bucket=settings.nebius_bucket, Key=key)
        return True
    except ClientError as err:
        if err.response["Error"]["Code"] == "404":
            return False
        raise


@task(retries=3, retry_delay_seconds=10)
def list_new_videos() -> list[str]:
    """List video files waiting in the video inbox prefix."""
    logger = get_run_logger()
    keys = _list_keys(settings.video_prefix)
    video_keys = [
        key for key in keys if any(key.endswith(ext) for ext in settings.video_extensions)
    ]
    logger.info("Found %s new video files", len(video_keys))
    return video_keys


@task(retries=3, retry_delay_seconds=10)
def list_new_audio() -> list[str]:
    """List audio files waiting in the audio inbox prefix."""
    logger = get_run_logger()
    keys = _list_keys(settings.audio_prefix)
    audio_keys = [
        key for key in keys if any(key.endswith(ext) for ext in settings.audio_extensions)
    ]
    logger.info("Found %s new audio files", len(audio_keys))
    return audio_keys


@task(retries=2, retry_delay_seconds=5)
def move_object(source_key: str, dest_prefix: str) -> str:
    """Move an object between prefixes with S3 copy and delete semantics."""
    bucket = settings.nebius_bucket
    dest_key = f"{dest_prefix}{_filename(source_key)}"
    s3 = get_s3_client()

    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": source_key},
        Key=dest_key,
    )
    s3.delete_object(Bucket=bucket, Key=source_key)

    get_run_logger().info("Moved s3://%s/%s to s3://%s/%s", bucket, source_key, bucket, dest_key)
    return dest_key


@task(retries=2, retry_delay_seconds=5)
def download_object(key: str, local_path: str) -> str:
    """Download an object for the optional local development flow."""
    get_s3_client().download_file(settings.nebius_bucket, key, local_path)
    return local_path


@task(retries=2, retry_delay_seconds=10)
def upload_object(local_path: str, key: str) -> str:
    """Upload an object for the optional local development flow."""
    get_s3_client().upload_file(local_path, settings.nebius_bucket, key)
    return key
