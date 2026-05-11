"""Nebius AI Job tasks for cloud audio extraction and transcription."""

import asyncio
from datetime import timedelta

from nebius.api.nebius.ai.v1 import (
    CreateJobRequest,
    GetJobRequest,
    Job,
    JobServiceClient,
    JobSpec,
    JobStatus,
)
from nebius.api.nebius.common.v1 import ResourceMetadata
from nebius.api.nebius.compute.v1 import DiskSpec as ComputeDiskSpec
from nebius.sdk import SDK
from prefect import task
from prefect.logging import get_run_logger

from nebius_pipeline.config import settings
from nebius_pipeline.tasks.extract import video_key_to_audio_key


def get_sdk() -> SDK:
    """Create an authenticated Nebius SDK client."""
    return SDK(credentials=settings.nebius_iam_token)


_TERMINAL_STATES = {
    JobStatus.State.COMPLETED,
    JobStatus.State.FAILED,
    JobStatus.State.CANCELLED,
    JobStatus.State.ERROR,
}


def _disk_spec() -> JobSpec.DiskSpec:
    return JobSpec.DiskSpec(
        type=ComputeDiskSpec.DiskType.NETWORK_SSD,
        size_bytes=settings.job_disk_gib * 1024 * 1024 * 1024,
    )


def _bucket_volume() -> list[JobSpec.VolumeMount]:
    return [
        JobSpec.VolumeMount(
            source=settings.nebius_bucket_id,
            container_path="/data",
            mode=JobSpec.VolumeMount.Mode.READ_WRITE,
        )
    ]


@task(retries=2, retry_delay_seconds=30)
async def create_ffmpeg_job(video_key: str) -> str:
    """Create a CPU job that extracts audio from a video in Object Storage."""
    logger = get_run_logger()
    sdk = get_sdk()

    try:
        filename = video_key.rsplit("/", 1)[-1]
        stem = filename.rsplit(".", 1)[0]
        container_video_path = f"/data/{video_key}"
        container_audio_path = f"/data/{video_key_to_audio_key(video_key)}"
        local_audio_path = f"/work/{stem}.mp3"

        command = (
            f'-lc "mkdir -p /work /data/{settings.audio_prefix.rstrip("/")} '
            f"&& ffmpeg -i '{container_video_path}' -vn -q:a 2 -y '{local_audio_path}' "
            f"&& cp '{local_audio_path}' '{container_audio_path}'\""
        )

        operation = await JobServiceClient(sdk).create(
            CreateJobRequest(
                metadata=ResourceMetadata(
                    parent_id=settings.nebius_project_id,
                    name=f"ffmpeg-{stem}",
                ),
                spec=JobSpec(
                    image=settings.ffmpeg_image,
                    container_command=settings.ffmpeg_container_command,
                    args=command,
                    platform=settings.cpu_platform,
                    preset=settings.cpu_preset,
                    subnet_id=settings.nebius_subnet_id,
                    timeout=timedelta(minutes=settings.job_timeout_minutes),
                    disk=_disk_spec(),
                    volumes=_bucket_volume(),
                ),
            )
        )

        await operation.wait()
        logger.info("Created ffmpeg job %s for %s", operation.resource_id, video_key)
        return operation.resource_id

    finally:
        await sdk.close()


@task(retries=2, retry_delay_seconds=30)
async def create_whisper_job(audio_key: str) -> str:
    """Create a GPU job that transcribes an audio file with Whisper."""
    logger = get_run_logger()
    sdk = get_sdk()

    try:
        stem = audio_key.rsplit("/", 1)[-1].rsplit(".", 1)[0]

        operation = await JobServiceClient(sdk).create(
            CreateJobRequest(
                metadata=ResourceMetadata(
                    parent_id=settings.nebius_project_id,
                    name=f"whisper-{stem}",
                ),
                spec=JobSpec(
                    image=settings.whisper_image,
                    args=f"/data/{audio_key}",
                    platform=settings.gpu_platform,
                    preset=settings.gpu_preset,
                    subnet_id=settings.nebius_subnet_id,
                    timeout=timedelta(minutes=settings.job_timeout_minutes),
                    disk=_disk_spec(),
                    volumes=_bucket_volume(),
                ),
            )
        )

        await operation.wait()
        logger.info("Created Whisper job %s for %s", operation.resource_id, audio_key)
        return operation.resource_id

    finally:
        await sdk.close()


@task(retries=5, retry_delay_seconds=60)
async def get_job_status(job_id: str) -> dict[str, str | bool]:
    """Read the current Nebius AI Job state."""
    sdk = get_sdk()
    try:
        job: Job = await JobServiceClient(sdk).get(GetJobRequest(id=job_id))
        state = job.status.state if job.status else JobStatus.State.STATE_UNSPECIFIED
        return {
            "job_id": job_id,
            "state": state.name,
            "done": state in _TERMINAL_STATES,
        }
    finally:
        await sdk.close()


@task
async def wait_for_job_completion(
    job_id: str,
    poll_seconds: int = 15,
    max_polls: int = 120,
) -> dict[str, str | bool]:
    """Wait until the job workload reaches a terminal state."""
    logger = get_run_logger()

    for _ in range(max_polls):
        status = await get_job_status.fn(job_id)
        state = status["state"]

        if status["done"]:
            if state != JobStatus.State.COMPLETED.name:
                raise RuntimeError(f"Job {job_id} finished unsuccessfully: {state}")
            logger.info("Job %s completed", job_id)
            return status

        await asyncio.sleep(poll_seconds)

    raise TimeoutError(
        f"Job {job_id} did not complete after {max_polls * poll_seconds} seconds"
    )
