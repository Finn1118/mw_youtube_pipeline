from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from speaker_extraction import extract_speakers
from speaker_extraction.cache import list_cached, update_speaker_names
from speaker_extraction.errors import (
    NoSpeakersDetectedError,
    SpeakerExtractionError,
    TranscriptionError,
    VideoUnavailableError,
)
from speaker_extraction.types import ExtractionRequest, ExtractionResult


class SpeakerRename(BaseModel):
    speaker_id: int
    name: str = Field(min_length=1, max_length=200)


class RenamePayload(BaseModel):
    renames: list[SpeakerRename]

app = FastAPI(title="Speaker Extraction API")

# Allow the millionways-platform Vue dev server (Vite default port) to call us
# directly during local development. Add other origins here as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _thumbnail_for(video_id: str, info: dict[str, Any]) -> str:
    thumb = info.get("thumbnail")
    if isinstance(thumb, str) and thumb:
        return thumb
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _library_video(item: dict[str, Any]) -> dict[str, Any]:
    info = item.get("info") or {}
    result = item.get("result") or {}
    video_id = str(item["video_id"])
    speakers = []
    for speaker in result.get("speakers", []):
        if not isinstance(speaker, dict):
            continue
        speakers.append(
            {
                "speaker_id": speaker.get("speaker_id"),
                "name": speaker.get("name", "Unknown"),
                "word_count": speaker.get("word_count", 0),
                "duration_seconds": speaker.get("duration_seconds", 0.0),
                "preview": speaker.get("preview", ""),
                "full_text": speaker.get("text", ""),
            }
        )

    return {
        "video_id": video_id,
        "source_url": result.get("source_url") or info.get("webpage_url") or "",
        "title": result.get("title") or info.get("title") or video_id,
        "uploader": result.get("uploader") or info.get("uploader") or info.get("channel") or "",
        "thumbnail": _thumbnail_for(video_id, info),
        "duration_seconds": result.get("duration_seconds") or info.get("duration") or 0.0,
        "transcribed_at": item.get("transcribed_at"),
        "speakers": speakers,
    }


@app.exception_handler(VideoUnavailableError)
async def video_unavailable_handler(
    request: Request, exc: VideoUnavailableError
) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=404,
        content={"detail": "Could not access this video. Check the URL or try again soon."},
    )


@app.exception_handler(NoSpeakersDetectedError)
async def no_speakers_handler(
    request: Request, exc: NoSpeakersDetectedError
) -> JSONResponse:
    _ = request, exc
    return JSONResponse(status_code=422, content={"detail": "No speech detected."})


@app.exception_handler(TranscriptionError)
async def transcription_handler(request: Request, exc: TranscriptionError) -> JSONResponse:
    _ = request, exc
    return JSONResponse(status_code=502, content={"detail": "Transcription failed. Try again."})


@app.exception_handler(SpeakerExtractionError)
async def extraction_handler(request: Request, exc: SpeakerExtractionError) -> JSONResponse:
    _ = request, exc
    return JSONResponse(status_code=500, content={"detail": "Speaker extraction failed."})


@app.post("/extract", response_model=ExtractionResult)
async def extract_endpoint(req: ExtractionRequest) -> ExtractionResult:
    return await extract_speakers(req)


@app.get("/library")
async def library_endpoint() -> dict[str, list[dict[str, Any]]]:
    videos = [_library_video(item) for item in list_cached()]
    return {"videos": videos}


@app.patch("/library/{video_id}/speakers")
async def rename_speakers_endpoint(video_id: str, payload: RenamePayload) -> dict[str, Any]:
    """Rename or swap speaker labels for a cached video. Idempotent."""
    name_by_id = {item.speaker_id: item.name.strip() for item in payload.renames}
    if not name_by_id:
        raise HTTPException(status_code=400, detail="No renames provided.")
    updated = update_speaker_names(video_id, name_by_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Video not found in library.")
    return {
        "video_id": video_id,
        "speakers": [
            {"speaker_id": speaker.get("speaker_id"), "name": speaker.get("name")}
            for speaker in updated.get("speakers", [])
            if isinstance(speaker, dict)
        ],
    }


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
