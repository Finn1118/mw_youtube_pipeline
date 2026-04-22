from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp

from .errors import VideoUnavailableError


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
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            safe_info = ydl.sanitize_info(info)
    except yt_dlp.utils.DownloadError as exc:
        raise VideoUnavailableError(str(exc)) from exc

    return path, safe_info
