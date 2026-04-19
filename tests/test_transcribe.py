from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from speaker_extraction.errors import TranscriptionError

transcribe_module = importlib.import_module("speaker_extraction.transcribe")
transcribe = transcribe_module.transcribe


def test_transcribe_happy_path(monkeypatch, tmp_path: Path) -> None:
    audio_file = tmp_path / "sample.m4a"
    audio_file.write_bytes(b"audio-bytes")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")

    class FakeResponse:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {"results": {"utterances": [{"speaker": 0, "start": 0, "end": 1}]}}

    def fake_post(url: str, **kwargs):
        assert url == "https://api.deepgram.com/v1/listen"
        assert kwargs["params"]["model"] == "nova-3"
        assert kwargs["headers"]["Authorization"] == "Token test-key"
        return FakeResponse()

    monkeypatch.setattr(transcribe_module.httpx, "post", fake_post)
    result = transcribe(audio_file)
    assert "results" in result


def test_transcribe_wraps_error(monkeypatch, tmp_path: Path) -> None:
    audio_file = tmp_path / "sample.m4a"
    audio_file.write_bytes(b"audio-bytes")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")

    def fake_post(url: str, **kwargs):
        _ = url, kwargs
        raise RuntimeError("api down")

    monkeypatch.setattr(transcribe_module.httpx, "post", fake_post)
    with pytest.raises(TranscriptionError):
        transcribe(audio_file)


def test_transcribe_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    audio_file = tmp_path / "sample.m4a"
    audio_file.write_bytes(b"audio-bytes")
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises(TranscriptionError, match="DEEPGRAM_API_KEY is not set"):
        transcribe(audio_file)
