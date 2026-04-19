from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - environment dependent
    OpenAI = None  # type: ignore[assignment]


INTRO_PATTERNS = (
    re.compile(r"\bjoe rogan podcast\b", re.IGNORECASE),
    re.compile(r"\bjoe rogan experience\b", re.IGNORECASE),
    re.compile(r"\b(?:check it out|showing by day|by night)\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\b.*\bnotifications\b", re.IGNORECASE),
    re.compile(r"\bwelcome back to\b", re.IGNORECASE),
)


def _is_intro_line(text: str) -> bool:
    """Detect pre-recorded intros/outros that pollute speaker attribution."""
    cleaned = text.strip()
    if not cleaned:
        return True
    for pattern in INTRO_PATTERNS:
        if pattern.search(cleaned):
            return True
    return False


def _build_snippet(utterances: list[dict[str, Any]], seconds: float = 120) -> str:
    """Compact 'Speaker N: ...' preview of the first ~N seconds."""
    lines: list[str] = []
    last_speaker: int | None = None

    for utterance in utterances:
        if utterance["start"] > seconds:
            break
        speaker = utterance["speaker"]
        transcript = utterance.get("transcript", "").strip()
        if not transcript:
            continue

        if speaker != last_speaker:
            lines.append(f"Speaker {speaker}: {transcript}")
            last_speaker = speaker
        else:
            lines[-1] += " " + transcript

    return "\n".join(lines)


def _speaker_stats(utterances: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    """Aggregate word count, duration, and first-appearance timestamp per speaker."""
    stats: dict[int, dict[str, float]] = defaultdict(
        lambda: {"words": 0, "duration": 0.0, "first_start": float("inf"), "utterances": 0}
    )
    for utterance in utterances:
        speaker = utterance["speaker"]
        text = utterance.get("transcript", "")
        stats[speaker]["words"] += len(text.split())
        stats[speaker]["duration"] += max(0.0, utterance["end"] - utterance["start"])
        stats[speaker]["utterances"] += 1
        if utterance["start"] < stats[speaker]["first_start"]:
            stats[speaker]["first_start"] = utterance["start"]
    return dict(stats)


def _sample_speaker_lines(
    utterances: list[dict[str, Any]],
    speaker: int,
    max_chars: int = 1800,
    max_lines: int = 12,
) -> list[str]:
    """Pick representative lines for a speaker, spread across the whole recording.

    Because a guest may be absent for long stretches, we filter to utterances where
    the given speaker actually spoke, then sample evenly across that filtered list.
    Short/filler utterances and obvious intro/outro lines are skipped.
    """
    owned = [
        utterance
        for utterance in utterances
        if utterance["speaker"] == speaker
        and utterance.get("transcript", "").strip()
        and not _is_intro_line(utterance.get("transcript", ""))
        and len(utterance.get("transcript", "").split()) >= 4
    ]
    if not owned:
        return []

    if len(owned) <= max_lines:
        picked = owned
    else:
        step = len(owned) / max_lines
        picked = [owned[int(i * step)] for i in range(max_lines)]

    out: list[str] = []
    used = 0
    for utterance in picked:
        text = utterance.get("transcript", "").strip()
        if not text:
            continue
        stamp = _format_timestamp(utterance["start"])
        line = f"[{stamp}] {text}"
        if used + len(line) > max_chars:
            break
        out.append(line)
        used += len(line)
    return out


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _build_identification_context(
    utterances: list[dict[str, Any]], video_info: dict[str, Any]
) -> str:
    """Assemble a rich, per-speaker context block for the LLM."""
    stats = _speaker_stats(utterances)
    total_duration = sum(s["duration"] for s in stats.values()) or 1.0

    sections: list[str] = []
    for speaker in sorted(stats.keys()):
        s = stats[speaker]
        share = 100.0 * s["duration"] / total_duration
        header = (
            f"Speaker {speaker}: {int(s['words'])} words, "
            f"{s['duration']:.0f}s total ({share:.0f}% of dialogue), "
            f"{int(s['utterances'])} utterances, "
            f"first heard at {_format_timestamp(s['first_start'])}."
        )
        samples = _sample_speaker_lines(utterances, speaker)
        if samples:
            body = "\n".join(f"  {line}" for line in samples)
            sections.append(f"{header}\nSamples spread across the video:\n{body}")
        else:
            sections.append(header)

    opening = _build_snippet(utterances, seconds=120)
    title = video_info.get("title") or ""
    uploader = video_info.get("uploader") or video_info.get("channel") or ""
    description = (video_info.get("description") or "")[:2000]

    return (
        f"YouTube title: {title}\n"
        f"Channel / uploader: {uploader}\n"
        f"Description (truncated):\n{description}\n\n"
        f"Diarized opening (first 2 minutes, for context only):\n{opening}\n\n"
        f"Per-speaker profile (use these samples and stats to identify each speaker):\n"
        + "\n\n".join(sections)
    )


IDENTIFY_SYSTEM_PROMPT = (
    "You identify the real-world names of diarized podcast speakers. "
    "Return a JSON object with a single key 'mapping' whose value maps each "
    "numeric speaker id present in the input (as a string key) to that person's "
    "full real name, or 'Unknown' if you cannot determine it confidently. "
    "Example: {\"mapping\": {\"0\": \"Joe Rogan\", \"1\": \"Sam Altman\"}}. "
    "Respond with JSON only, no prose."
)


IDENTIFY_USER_INSTRUCTIONS = """Determine who each numeric Speaker ID corresponds to. Reason carefully using ALL of the clues below.

Strong clues (use these first):
- The YouTube title and description usually name the host and featured guest(s) explicitly.
- The channel/uploader name usually corresponds to the host. The host may not be the first person heard -- pre-recorded intro voiceovers, songs, or clips often play before anyone speaks live. Treat "Speaker who said the intro" as NOT strong evidence.
- Speakers' samples are drawn from across the whole video. Read them for content clues:
  * Who is asking questions versus giving long explanations? Interviewers ask; guests explain their work.
  * Who says "thanks for having me" / "great to be here"? That is almost always the guest.
  * Who is addressed by name (e.g. "So, Sam, you were saying...") by someone else? The addressed speaker is the one named.
  * Who describes companies, products, or projects in the first person ("we built...", "at my company...")? That speaker is likely the person associated with that work.
- On interview shows, the guest usually speaks MORE total time than the host, but a guest may be silent for long stretches, and a host may deliver long monologues during the intro.

Rules:
- Diarization can be noisy. A single utterance sometimes contains words from two people. Do not over-anchor on any one line; weigh the full profile.
- If two speaker ids have overlapping or similar content, assign the name that fits the majority of each speaker's samples.
- Use "Unknown" rather than guessing when the clues conflict or the person is genuinely unnameable (a random caller, unnamed co-host, etc.).
- Return ONLY the JSON object described in the system message. Do not include explanations.
"""


def identify_speakers(
    utterances: list[dict[str, Any]],
    video_info: dict[str, Any],
    model: str = "gpt-5.4-mini",
) -> dict[int, str]:
    """Map Deepgram speaker IDs to real names via LLM."""
    if OpenAI is None:
        raise RuntimeError("openai package is not installed.")
    client = OpenAI()
    context = _build_identification_context(utterances, video_info)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": IDENTIFY_SYSTEM_PROMPT},
            {"role": "user", "content": IDENTIFY_USER_INSTRUCTIONS + "\n\n" + context},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    raw = parsed.get("mapping") if isinstance(parsed, dict) else None
    if isinstance(raw, dict):
        return {int(key): str(value) for key, value in raw.items() if str(key).isdigit()}
    if isinstance(parsed, dict):
        return {int(key): str(value) for key, value in parsed.items() if str(key).isdigit()}
    return {}


def _needs_escalation(mapping: dict[int, str]) -> bool:
    """Trigger a stronger model when the cheap pass looks weak."""
    if not mapping:
        return True
    if all(value == "Unknown" for value in mapping.values()):
        return True
    values = [value.strip() for value in mapping.values()]
    unique_non_unknown = {value for value in values if value and value != "Unknown"}
    if len(unique_non_unknown) < len([v for v in values if v and v != "Unknown"]):
        return True
    return False


def identify_with_fallback(
    utterances: list[dict[str, Any]],
    video_info: dict[str, Any],
) -> dict[int, str]:
    """Use mini by default; escalate if the result looks weak or ambiguous."""
    mapping = identify_speakers(utterances, video_info, model="gpt-5.4-mini")
    if _needs_escalation(mapping):
        stronger = identify_speakers(utterances, video_info, model="gpt-5.4")
        if stronger:
            mapping = stronger
    return mapping
