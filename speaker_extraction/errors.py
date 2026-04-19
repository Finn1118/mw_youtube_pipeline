class SpeakerExtractionError(Exception):
    """Base exception for the module."""


class VideoUnavailableError(SpeakerExtractionError):
    """yt-dlp failed to fetch (private, age-gated, region-locked, removed)."""


class TranscriptionError(SpeakerExtractionError):
    """Deepgram failed to transcribe."""


class NoSpeakersDetectedError(SpeakerExtractionError):
    """Diarization returned zero usable speakers."""
