from __future__ import annotations

from collections import defaultdict
from typing import Any

from .errors import NoSpeakersDetectedError
from .types import SpeakerText


def assemble_speakers(
    utterances: list[dict[str, Any]],
    name_mapping: dict[int, str],
    min_seconds: float = 30.0,
) -> list[SpeakerText]:
    """Group utterances by speaker, compute stats, sort by duration DESC."""
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for utterance in utterances:
        buckets[utterance["speaker"]].append(utterance)

    speakers: list[SpeakerText] = []
    for speaker_id, utterance_group in buckets.items():
        text = " ".join(item.get("transcript", "") for item in utterance_group).strip()
        if not text:
            continue

        duration = sum(item["end"] - item["start"] for item in utterance_group)
        if duration < min_seconds:
            continue

        word_count = sum(len(item.get("transcript", "").split()) for item in utterance_group)
        avg_conf = sum(item.get("confidence", 0.0) for item in utterance_group) / len(
            utterance_group
        )

        preview = text[:200].rstrip() + ("..." if len(text) > 200 else "")
        speakers.append(
            SpeakerText(
                speaker_id=speaker_id,
                name=name_mapping.get(speaker_id, "Unknown"),
                text=text,
                word_count=word_count,
                duration_seconds=round(duration, 2),
                avg_confidence=round(avg_conf, 4),
                preview=preview,
            )
        )

    if not speakers:
        raise NoSpeakersDetectedError(
            "Diarization returned no speakers above the minimum duration threshold."
        )

    speakers.sort(key=lambda speaker: speaker.duration_seconds, reverse=True)
    return speakers
