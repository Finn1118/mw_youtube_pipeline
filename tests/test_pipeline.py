from __future__ import annotations

from pathlib import Path

from speaker_extraction import ExtractionRequest, extract_speakers


async def test_extract_speakers_end_to_end_mocked(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPEAKER_CACHE_PATH", str(tmp_path / "cache.sqlite"))

    sample_info = {
        "id": "abcdefghijk",
        "title": "Mocked Episode",
        "uploader": "Host Name",
        "description": "Mocked test description",
        "duration": 100.0,
    }
    sample_utterances = [
        {
            "speaker": 0,
            "start": 0.0,
            "end": 40.0,
            "transcript": "host text",
            "confidence": 0.95,
        },
        {
            "speaker": 1,
            "start": 40.0,
            "end": 85.0,
            "transcript": "guest text",
            "confidence": 0.94,
        },
    ]

    def fake_fetch_audio(url: str, workdir: Path):
        _ = workdir
        return Path(url), sample_info

    def fake_transcribe(audio_path: Path):
        _ = audio_path
        return {"results": {"utterances": sample_utterances}}

    def fake_identify(utterances, info):
        _ = utterances, info
        return {0: "Host Name", 1: "Guest Name"}

    monkeypatch.setattr("speaker_extraction.fetch_audio", fake_fetch_audio)
    monkeypatch.setattr("speaker_extraction.transcribe", fake_transcribe)
    monkeypatch.setattr("speaker_extraction.identify_with_fallback", fake_identify)

    req = ExtractionRequest(
        url="https://youtube.com/watch?v=abcdefghijk",
        min_speaker_seconds=0.0,
    )
    result = await extract_speakers(req)
    assert result.video_id == "abcdefghijk"
    assert len(result.speakers) == 2
    assert {s.name for s in result.speakers} == {"Host Name", "Guest Name"}
