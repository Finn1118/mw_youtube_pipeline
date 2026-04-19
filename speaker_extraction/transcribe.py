from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from .errors import TranscriptionError


def transcribe(audio_path: Path) -> dict[str, Any]:
    """Submit audio to Deepgram Nova-3 with diarization."""
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise TranscriptionError("DEEPGRAM_API_KEY is not set.")

    content_type = "audio/m4a" if audio_path.suffix.lower() == ".m4a" else "audio/webm"
    params = {
        "model": "nova-3",
        "language": "en",
        "diarize": "true",
        "smart_format": "true",
        "punctuate": "true",
        "utterances": "true",
        "utt_split": "0.5",
        "paragraphs": "true",
        "filler_words": "true",
        "numerals": "true",
    }

    try:
        with open(audio_path, "rb") as handle:
            response = httpx.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": content_type,
                },
                content=handle.read(),
                timeout=httpx.Timeout(600.0, connect=30.0),
            )
        response.raise_for_status()
        payload = response.json()
        if "results" not in payload:
            raise TranscriptionError(
                f"Deepgram response missing 'results'. Keys: {sorted(payload.keys())}"
            )
        return payload
    except Exception as exc:  # pragma: no cover - wrapped for typed handling
        raise TranscriptionError(str(exc)) from exc
