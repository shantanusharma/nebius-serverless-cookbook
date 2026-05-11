"""CLI entrypoint for the video transcription pipeline."""

import asyncio
import sys

from nebius_pipeline.flows import (
    check_bucket,
    extract_audio_cloud_flow,
    fully_cloud_pipeline,
    hybrid_pipeline,
)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"

    if command == "check":
        print(f"\nResult: {check_bucket()}")
    elif command == "cloud-extract":
        print(f"\nResult: {asyncio.run(extract_audio_cloud_flow())}")
    elif command == "cloud-run":
        print(f"\nResult: {asyncio.run(fully_cloud_pipeline())}")
    elif command == "run":
        print(f"\nResult: {asyncio.run(hybrid_pipeline())}")
    elif command == "serve":
        fully_cloud_pipeline.serve(
            name="video-transcription-pipeline",
            cron="*/15 * * * *",
            tags=["nebius", "prefect", "transcription", "mlops"],
        )
    else:
        print("Usage: python -m nebius_pipeline [check|cloud-extract|cloud-run|run|serve]")
        sys.exit(1)


if __name__ == "__main__":
    main()
