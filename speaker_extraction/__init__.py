from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache import get_cached, init_db, save_cache
from .errors import (
    NoSpeakersDetectedError,
    SpeakerExtractionError,
    TranscriptionError,
    VideoUnavailableError,
)
from .extract import assemble_speakers
from .fetch import fetch_audio
from .identify import identify_with_fallback
from .transcribe import transcribe
from .types import ExtractionRequest, ExtractionResult, SpeakerText


async def extract_speakers(req: ExtractionRequest) -> ExtractionResult:
    """Main entry point. Runs blocking I/O in a thread."""
    return await asyncio.to_thread(_run_pipeline, req)


def _run_pipeline(req: ExtractionRequest) -> ExtractionResult:
    init_db()
    cached = None if req.force_refresh else get_cached(req.url)

    if cached:
        cached_result = cached.get("result")
        cached_min_seconds = cached.get("min_speaker_seconds")
        cached_language = cached.get("language")
        if (
            isinstance(cached_result, dict)
            and cached_min_seconds == req.min_speaker_seconds
            and cached_language == req.language
        ):
            return ExtractionResult.model_validate(cached_result)
        info = cached["info"]
        utterances = cached["utterances"]
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path, info = fetch_audio(req.url, Path(tmpdir))
            dg_response = transcribe(audio_path)
        utterances = _extract_utterances(dg_response)
        save_cache(req.url, info, utterances)

    name_mapping = identify_with_fallback(utterances, info)
    speakers = assemble_speakers(utterances, name_mapping, req.min_speaker_seconds)

    result = ExtractionResult(
        video_id=info["id"],
        source_url=req.url,
        title=info.get("title", ""),
        uploader=info.get("uploader") or info.get("channel") or "",
        description=info.get("description") or "",
        duration_seconds=float(info.get("duration") or 0),
        language=req.language,
        speakers=speakers,
        processed_at=datetime.now(timezone.utc),
    )
    save_cache(
        req.url,
        info,
        utterances,
        result_data=result.model_dump(mode="json"),
        min_speaker_seconds=req.min_speaker_seconds,
        language=req.language,
    )
    return result


def _extract_utterances(dg_response: dict[str, Any]) -> list[dict[str, Any]]:
    results = dg_response.get("results")
    if not isinstance(results, dict):
        raise TranscriptionError("Deepgram response missing 'results'.")

    utterances = results.get("utterances")
    if not isinstance(utterances, list):
        raise TranscriptionError("Deepgram response missing 'results.utterances'.")
    return utterances


__all__ = [
    "extract_speakers",
    "ExtractionRequest",
    "ExtractionResult",
    "SpeakerText",
    "SpeakerExtractionError",
    "VideoUnavailableError",
    "TranscriptionError",
    "NoSpeakersDetectedError",
]
