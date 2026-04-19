from datetime import datetime

from pydantic import BaseModel


class ExtractionRequest(BaseModel):
    url: str
    language: str = "en"
    force_refresh: bool = False
    min_speaker_seconds: float = 30.0


class SpeakerText(BaseModel):
    speaker_id: int
    name: str
    text: str
    word_count: int
    duration_seconds: float
    avg_confidence: float
    preview: str


class ExtractionResult(BaseModel):
    video_id: str
    source_url: str
    title: str
    uploader: str
    description: str
    duration_seconds: float
    language: str
    speakers: list[SpeakerText]
    processed_at: datetime
    deepgram_model: str = "nova-3"
    mapping_model: str = "gpt-5.4-nano"
