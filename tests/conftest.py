from __future__ import annotations

import pytest


@pytest.fixture
def sample_utterances() -> list[dict]:
    return [
        {
            "speaker": 0,
            "start": 0.0,
            "end": 5.0,
            "transcript": "Welcome back to the show.",
            "confidence": 0.96,
        },
        {
            "speaker": 1,
            "start": 5.0,
            "end": 12.0,
            "transcript": "Thanks for having me, this is great.",
            "confidence": 0.94,
        },
        {
            "speaker": 0,
            "start": 12.0,
            "end": 22.0,
            "transcript": "What are you building this year?",
            "confidence": 0.95,
        },
        {
            "speaker": 1,
            "start": 22.0,
            "end": 35.0,
            "transcript": "We are focusing on model tooling and evaluations.",
            "confidence": 0.93,
        },
        {
            "speaker": 1,
            "start": 35.0,
            "end": 50.0,
            "transcript": "The roadmap is pretty ambitious.",
            "confidence": 0.92,
        },
        {
            "speaker": 0,
            "start": 50.0,
            "end": 65.0,
            "transcript": "That is exciting to hear.",
            "confidence": 0.97,
        },
    ]


@pytest.fixture
def video_info() -> dict:
    return {
        "id": "abcdefghijk",
        "title": "Sample Interview Episode",
        "uploader": "Sample Host",
        "description": "A practical interview about building AI products.",
        "duration": 3900,
    }
