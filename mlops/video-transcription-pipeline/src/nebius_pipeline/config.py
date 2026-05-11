"""Configuration for the video transcription pipeline."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Pipeline configuration loaded from environment variables."""

    nebius_iam_token: str = Field(default="", validation_alias="NEBIUS_IAM_TOKEN")

    nebius_project_id: str = ""
    nebius_subnet_id: str = ""
    nebius_bucket_id: str = ""

    nebius_bucket: str = ""
    nebius_endpoint: str = "https://storage.eu-north1.nebius.cloud"
    nebius_region: str = "eu-north1"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    video_prefix: str = "video/"
    audio_prefix: str = "audio/"
    done_video_prefix: str = "DONE_video/"
    done_audio_prefix: str = "DONE_audio/"

    ffmpeg_image: str = "lscr.io/linuxserver/ffmpeg:latest"
    ffmpeg_container_command: str = "sh"
    whisper_image: str = "ghcr.io/darko-mesaros/nebius-whisper:latest"

    cpu_platform: str = "cpu-d3"
    cpu_preset: str = "4vcpu-16gb"
    gpu_platform: str = "gpu-h200-sxm"
    gpu_preset: str = "1gpu-16vcpu-200gb"
    job_timeout_minutes: int = 30
    job_disk_gib: int = 250

    video_extensions: list[str] = [".mp4", ".mkv", ".mov"]
    audio_extensions: list[str] = [".mp3", ".m4a", ".wav", ".flac", ".ogg"]

    model_config = {
        "env_prefix": "NEBIUS_PIPELINE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
