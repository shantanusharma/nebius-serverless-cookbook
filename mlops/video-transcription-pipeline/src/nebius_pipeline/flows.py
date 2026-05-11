"""Prefect flows for the video transcription pipeline."""

from prefect import flow
from prefect.logging import get_run_logger

from nebius_pipeline.config import settings
from nebius_pipeline.tasks.extract import (
    build_local_paths,
    run_ffmpeg_extraction,
    upload_extracted_audio,
    video_key_to_audio_key,
)
from nebius_pipeline.tasks.jobs import (
    create_ffmpeg_job,
    create_whisper_job,
    wait_for_job_completion,
)
from nebius_pipeline.tasks.storage import (
    download_object,
    list_new_audio,
    list_new_videos,
    move_object,
    object_exists,
)


@flow(name="Fully Cloud Video Transcription Pipeline", log_prints=True)
async def fully_cloud_pipeline() -> dict:
    """Extract audio in a CPU job, transcribe it in a GPU job, and archive outputs."""
    logger = get_run_logger()

    new_videos = list_new_videos()
    extracted_audio = []
    ffmpeg_job_ids = []

    for video_key in new_videos:
        job_id = await create_ffmpeg_job(video_key)
        ffmpeg_job_ids.append(job_id)
        await wait_for_job_completion(job_id)

        move_object(video_key, settings.done_video_prefix)
        extracted_audio.append(video_key_to_audio_key(video_key))

    new_audio = list_new_audio()
    whisper_job_ids = []
    transcripts_moved = []

    for audio_key in new_audio:
        job_id = await create_whisper_job(audio_key)
        whisper_job_ids.append(job_id)
        await wait_for_job_completion(job_id)

        transcript_key = f"{audio_key.rsplit('.', 1)[0]}.txt"
        if object_exists(transcript_key):
            move_object(transcript_key, settings.done_audio_prefix)
            transcripts_moved.append(transcript_key)

        move_object(audio_key, settings.done_audio_prefix)

    summary = {
        "new_videos": len(new_videos),
        "audio_extracted": len(extracted_audio),
        "ffmpeg_jobs_created": len(ffmpeg_job_ids),
        "ffmpeg_job_ids": ffmpeg_job_ids,
        "new_audio": len(new_audio),
        "whisper_jobs_created": len(whisper_job_ids),
        "whisper_job_ids": whisper_job_ids,
        "transcripts_moved": len(transcripts_moved),
    }

    logger.info("Pipeline complete: %s", summary)
    return summary


@flow(name="Check Video Transcription Bucket", log_prints=True)
def check_bucket() -> dict:
    """Show what is waiting in the pipeline inbox prefixes."""
    summary = {
        "new_videos": list_new_videos(),
        "new_audio": list_new_audio(),
    }
    get_run_logger().info("Bucket status: %s", summary)
    return summary


@flow(name="Extract Audio In Cloud", log_prints=True)
async def extract_audio_cloud_flow() -> dict:
    """Run only the cloud audio extraction stage."""
    new_videos = list_new_videos()
    extracted_audio = []
    job_ids = []

    for video_key in new_videos:
        job_id = await create_ffmpeg_job(video_key)
        job_ids.append(job_id)
        await wait_for_job_completion(job_id)
        move_object(video_key, settings.done_video_prefix)
        extracted_audio.append(video_key_to_audio_key(video_key))

    return {
        "new_videos": len(new_videos),
        "audio_extracted": extracted_audio,
        "jobs_created": len(job_ids),
        "job_ids": job_ids,
    }


@flow(name="Hybrid Video Transcription Pipeline", log_prints=True)
async def hybrid_pipeline() -> dict:
    """Optional development flow that extracts audio locally and transcribes in the cloud."""
    new_videos = list_new_videos()
    extracted_audio = []

    for video_key in new_videos:
        paths = build_local_paths(video_key)
        audio_key = video_key_to_audio_key(video_key)
        download_object(video_key, paths["local_video"])
        run_ffmpeg_extraction(paths["local_video"], paths["local_audio"])
        upload_extracted_audio(paths["local_audio"], audio_key)
        move_object(video_key, settings.done_video_prefix)
        extracted_audio.append(audio_key)

    new_audio = list_new_audio()
    whisper_job_ids = []

    for audio_key in new_audio:
        job_id = await create_whisper_job(audio_key)
        whisper_job_ids.append(job_id)
        await wait_for_job_completion(job_id)

        transcript_key = f"{audio_key.rsplit('.', 1)[0]}.txt"
        if object_exists(transcript_key):
            move_object(transcript_key, settings.done_audio_prefix)
        move_object(audio_key, settings.done_audio_prefix)

    return {
        "new_videos": len(new_videos),
        "audio_extracted": len(extracted_audio),
        "new_audio": len(new_audio),
        "whisper_jobs_created": len(whisper_job_ids),
        "whisper_job_ids": whisper_job_ids,
    }
