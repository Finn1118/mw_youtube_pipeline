from __future__ import annotations

from pathlib import Path

from speaker_extraction import cache


def test_cache_roundtrip(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite"
    monkeypatch.setenv("SPEAKER_CACHE_PATH", str(db_path))

    url = "https://www.youtube.com/watch?v=abcdefghijk"
    info = {"id": "abcdefghijk", "title": "Demo"}
    utterances = [{"speaker": 0, "start": 0.0, "end": 2.0, "transcript": "hello"}]

    assert cache.get_cached(url) is None
    cache.save_cache(url, info, utterances)

    result = cache.get_cached(url)
    assert result is not None
    assert result["info"]["id"] == "abcdefghijk"
    assert result["utterances"][0]["speaker"] == 0


def test_cache_miss_for_non_youtube_url(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite"
    monkeypatch.setenv("SPEAKER_CACHE_PATH", str(db_path))
    assert cache.get_cached("https://example.com/video.mp4") is None


def test_update_speaker_names_patches_cached_result(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite"
    monkeypatch.setenv("SPEAKER_CACHE_PATH", str(db_path))

    url = "https://www.youtube.com/watch?v=abcdefghijk"
    info = {"id": "abcdefghijk", "title": "Demo"}
    utterances = [{"speaker": 0, "start": 0.0, "end": 2.0, "transcript": "hello"}]
    result_data = {
        "video_id": "abcdefghijk",
        "speakers": [
            {"speaker_id": 0, "name": "Wrong A"},
            {"speaker_id": 1, "name": "Wrong B"},
        ],
    }
    cache.save_cache(url, info, utterances, result_data=result_data)

    updated = cache.update_speaker_names(
        "abcdefghijk", {0: "Right A", 1: "Right B"}
    )
    assert updated is not None
    names_by_id = {s["speaker_id"]: s["name"] for s in updated["speakers"]}
    assert names_by_id == {0: "Right A", 1: "Right B"}

    reloaded = cache.get_cached(url)
    assert reloaded is not None
    reloaded_names = {s["speaker_id"]: s["name"] for s in reloaded["result"]["speakers"]}
    assert reloaded_names == {0: "Right A", 1: "Right B"}


def test_update_speaker_names_missing_video_returns_none(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite"
    monkeypatch.setenv("SPEAKER_CACHE_PATH", str(db_path))
    cache.init_db()
    assert cache.update_speaker_names("nope", {0: "Name"}) is None
