from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import _extract_video_id


def _cache_path() -> Path:
    return Path(os.getenv("SPEAKER_CACHE_PATH", "./.speaker_cache.sqlite"))


def _connect() -> sqlite3.Connection:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transcript_cache (
                video_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                transcribed_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_cached(url: str) -> dict[str, Any] | None:
    init_db()
    video_id = _extract_video_id(url)
    if not video_id:
        return None

    with _connect() as conn:
        row = conn.execute(
            "SELECT data FROM transcript_cache WHERE video_id = ?",
            (video_id,),
        ).fetchone()

    if not row:
        return None
    return json.loads(row[0])


def save_cache(
    url: str,
    info: dict[str, Any],
    utterances: list[dict[str, Any]],
    result_data: dict[str, Any] | None = None,
    min_speaker_seconds: float | None = None,
    language: str | None = None,
) -> None:
    init_db()
    _ = url
    video_id = info["id"]
    payload_dict: dict[str, Any] = {"info": info, "utterances": utterances, "model": "nova-3"}
    if result_data is not None:
        payload_dict["result"] = result_data
    if min_speaker_seconds is not None:
        payload_dict["min_speaker_seconds"] = min_speaker_seconds
    if language is not None:
        payload_dict["language"] = language

    payload = json.dumps(payload_dict, ensure_ascii=True)
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO transcript_cache (video_id, data, transcribed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                data = excluded.data,
                transcribed_at = excluded.transcribed_at
            """,
            (video_id, payload, now),
        )
        conn.commit()


def update_speaker_names(video_id: str, name_by_speaker_id: dict[int, str]) -> dict[str, Any] | None:
    """Patch the cached result's speaker names in place.

    Returns the updated result dict on success, or None if no row exists for that video.
    """
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT data FROM transcript_cache WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[0])
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        speakers = result.get("speakers", [])
        if not isinstance(speakers, list):
            return None
        for speaker in speakers:
            if not isinstance(speaker, dict):
                continue
            sid = speaker.get("speaker_id")
            if sid in name_by_speaker_id:
                speaker["name"] = str(name_by_speaker_id[sid])
        payload["result"] = result
        conn.execute(
            "UPDATE transcript_cache SET data = ? WHERE video_id = ?",
            (json.dumps(payload, ensure_ascii=True), video_id),
        )
        conn.commit()
    return result


def list_cached() -> list[dict[str, Any]]:
    """Return cached rows that contain a completed ExtractionResult payload."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT video_id, data, transcribed_at
            FROM transcript_cache
            ORDER BY transcribed_at DESC
            """
        ).fetchall()

    items: list[dict[str, Any]] = []
    for video_id, data, transcribed_at in rows:
        parsed = json.loads(data)
        result = parsed.get("result")
        if not isinstance(result, dict):
            continue
        items.append(
            {
                "video_id": video_id,
                "transcribed_at": transcribed_at,
                "info": parsed.get("info", {}),
                "result": result,
            }
        )
    return items
