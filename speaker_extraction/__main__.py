from __future__ import annotations

import argparse
import asyncio
import sys

from . import extract_speakers
from .errors import (
    NoSpeakersDetectedError,
    SpeakerExtractionError,
    TranscriptionError,
    VideoUnavailableError,
)
from .types import ExtractionRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract per-speaker transcripts from YouTube.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--language", default="en", help="Language hint for transcription")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass cache and force a fresh transcription",
    )
    parser.add_argument(
        "--min-seconds",
        dest="min_seconds",
        type=float,
        default=30.0,
        help="Minimum speaker duration threshold in seconds",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    request = ExtractionRequest(
        url=args.url,
        language=args.language,
        force_refresh=args.force_refresh,
        min_speaker_seconds=args.min_seconds,
    )

    try:
        result = await extract_speakers(request)
        print(result.model_dump_json(indent=2, ensure_ascii=True))
        return 0
    except VideoUnavailableError as exc:
        print(f"Video unavailable: {exc}", file=sys.stderr)
        return 2
    except TranscriptionError as exc:
        print(f"Transcription failed: {exc}", file=sys.stderr)
        return 3
    except NoSpeakersDetectedError as exc:
        print(f"No speakers detected: {exc}", file=sys.stderr)
        return 4
    except SpeakerExtractionError as exc:
        print(f"Speaker extraction failed: {exc}", file=sys.stderr)
        return 5


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
