from __future__ import annotations

from pathlib import Path

import pytest
import yt_dlp

from speaker_extraction.errors import VideoUnavailableError
from speaker_extraction.fetch import fetch_audio


def test_fetch_audio_happy_path(monkeypatch, tmp_path: Path) -> None:
    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def extract_info(self, url, download=True):
            _ = download
            return {"id": "abcdefghijk", "ext": "m4a", "title": "Demo", "url": url}

        def prepare_filename(self, info):
            return str(tmp_path / f"{info['id']}.{info['ext']}")

        def sanitize_info(self, info):
            return info

    monkeypatch.setattr("speaker_extraction.fetch.yt_dlp.YoutubeDL", FakeYDL)
    audio_path, info = fetch_audio("https://youtube.com/watch?v=abcdefghijk", tmp_path)
    assert audio_path.name == "abcdefghijk.m4a"
    assert info["id"] == "abcdefghijk"


def test_fetch_audio_wraps_download_error(monkeypatch, tmp_path: Path) -> None:
    class FakeYDL:
        def __init__(self, opts):
            _ = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def extract_info(self, url, download=True):
            _ = url, download
            raise yt_dlp.utils.DownloadError("not accessible")

    monkeypatch.setattr("speaker_extraction.fetch.yt_dlp.YoutubeDL", FakeYDL)
    with pytest.raises(VideoUnavailableError):
        fetch_audio("https://youtube.com/watch?v=abcdefghijk", tmp_path)
