from __future__ import annotations

import pytest

from speaker_extraction.errors import NoSpeakersDetectedError
from speaker_extraction.extract import assemble_speakers


def test_assemble_speakers_sorted_and_counts(sample_utterances: list[dict]) -> None:
    result = assemble_speakers(
        utterances=sample_utterances,
        name_mapping={0: "Host", 1: "Guest"},
        min_seconds=0.0,
    )
    assert len(result) == 2
    assert result[0].duration_seconds >= result[1].duration_seconds
    assert result[0].word_count > 0
    assert result[1].word_count > 0


def test_assemble_speakers_filters_below_threshold(sample_utterances: list[dict]) -> None:
    result = assemble_speakers(
        utterances=sample_utterances,
        name_mapping={0: "Host", 1: "Guest"},
        min_seconds=35.0,
    )
    assert len(result) == 1
    assert result[0].speaker_id == 1


def test_assemble_speakers_raises_when_empty() -> None:
    with pytest.raises(NoSpeakersDetectedError):
        assemble_speakers([], {}, min_seconds=0.0)


def test_preview_is_truncated() -> None:
    long_text = "word " * 120
    utterances = [
        {
            "speaker": 0,
            "start": 0.0,
            "end": 40.0,
            "transcript": long_text,
            "confidence": 0.9,
        }
    ]
    result = assemble_speakers(utterances, {0: "Host"}, min_seconds=0.0)
    assert len(result[0].preview) <= 203
    assert result[0].preview.endswith("...")
