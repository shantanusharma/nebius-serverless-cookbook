"""Optional local audio extraction helpers."""

import subprocess
import tempfile
from pathlib import Path

from prefect import task

from nebius_pipeline.config import settings
from nebius_pipeline.tasks.storage import upload_object


def video_key_to_audio_key(video_key: str) -> str:
    """Convert video/episode.mp4 into audio/episode.mp3."""
    filename = video_key.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    return f"{settings.audio_prefix}{stem}.mp3"


def build_local_paths(video_key: str) -> dict[str, str]:
    """Create repeatable temp paths for local extraction."""
    filename = video_key.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    tmpdir = Path(tempfile.gettempdir()) / "nebius-video-transcription"
    tmpdir.mkdir(parents=True, exist_ok=True)
    return {
        "local_video": str(tmpdir / filename),
        "local_audio": str(tmpdir / f"{stem}.mp3"),
    }


@task(retries=1, retry_delay_seconds=10)
def run_ffmpeg_extraction(local_video: str, local_audio: str) -> str:
    """Extract mp3 audio locally with ffmpeg."""
    result = subprocess.run(
        ["ffmpeg", "-i", local_video, "-vn", "-q:a", "2", "-y", local_audio],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed with exit {result.returncode}: {result.stderr[-500:]}")
    return local_audio


@task(retries=2, retry_delay_seconds=10)
def upload_extracted_audio(local_audio: str, audio_key: str) -> str:
    """Upload locally extracted audio back into Object Storage."""
    return upload_object.fn(local_audio, audio_key)
