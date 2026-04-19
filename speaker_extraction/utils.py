from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        candidate = parsed.path.strip("/").split("/")[0]
        return candidate if _YOUTUBE_ID_RE.match(candidate) else None

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            candidate = (query.get("v") or [None])[0]
            return candidate if candidate and _YOUTUBE_ID_RE.match(candidate) else None
        if parsed.path.startswith("/shorts/"):
            candidate = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else None
            return candidate if candidate and _YOUTUBE_ID_RE.match(candidate) else None
        if parsed.path.startswith("/embed/"):
            candidate = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else None
            return candidate if candidate and _YOUTUBE_ID_RE.match(candidate) else None

    return None
