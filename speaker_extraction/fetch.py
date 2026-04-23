from __future__ import annotations

import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp

from .errors import VideoUnavailableError

logger = logging.getLogger(__name__)

# Decoded once per process lifetime and written to a temp file.
_cookies_file: str | None = None


def _get_cookies_file() -> str | None:
    global _cookies_file
    if _cookies_file is not None:
        return _cookies_file
    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if not b64:
        logger.warning("YOUTUBE_COOKIES_B64 not set — yt-dlp will run without cookies")
        return None
    try:
        data = base64.b64decode(b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        tmp.write(data)
        tmp.close()
        _cookies_file = tmp.name
        logger.info("YouTube cookies loaded (%d bytes) -> %s", len(data), tmp.name)
    except Exception as exc:
        logger.error("Failed to decode YOUTUBE_COOKIES_B64: %s", exc)
        return None
    return _cookies_file


def fetch_audio(url: str, workdir: Path) -> tuple[Path, dict[str, Any]]:
    """Download audio-only stream and return (path, metadata)."""
    cookies_file = _get_cookies_file()
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # With cookies, use web client so auth is respected.
        # Without cookies, android_vr bypasses the JS challenge on residential IPs.
        "extractor_args": {"youtube": {"player_client": ["web"] if cookies_file else ["android_vr", "web"]}},
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            safe_info = ydl.sanitize_info(info)
    except yt_dlp.utils.DownloadError as exc:
        raise VideoUnavailableError(str(exc)) from exc

    return path, safe_info
