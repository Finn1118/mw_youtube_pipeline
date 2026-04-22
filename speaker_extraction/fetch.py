from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp

from .errors import VideoUnavailableError

# Decoded once per process lifetime and written to a temp file.
_cookies_file: str | None = None


def _get_cookies_file() -> str | None:
    global _cookies_file
    if _cookies_file is not None:
        return _cookies_file
    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if not b64:
        return None
    try:
        data = base64.b64decode(b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        tmp.write(data)
        tmp.close()
        _cookies_file = tmp.name
    except Exception:
        return None
    return _cookies_file


def fetch_audio(url: str, workdir: Path) -> tuple[Path, dict[str, Any]]:
    """Download audio-only stream and return (path, metadata)."""
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android_vr", "web"]}},
    }
    cookies_file = _get_cookies_file()
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
