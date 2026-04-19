# Speaker Extraction Module

Speaker extraction pipeline for YouTube URLs with:
- audio fetch via `yt-dlp`
- transcription + diarization via Deepgram Nova-3
- speaker-name mapping via OpenAI structured outputs
- per-speaker text aggregation for downstream profiling

## Requirements

- Python 3.11+
- Deno installed (required by modern `yt-dlp` for YouTube challenges)

## Environment

Copy `.env.example` to `.env` and set:

- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`
- `SPEAKER_CACHE_PATH` (optional, defaults to `./.speaker_cache.sqlite`)

## Install

```bash
pip install -r requirements.txt
```

## CLI usage

```bash
python -m speaker_extraction "https://www.youtube.com/watch?v=VIDEO_ID"
```

Optional flags:

```bash
python -m speaker_extraction "https://www.youtube.com/watch?v=VIDEO_ID" --language en --min-seconds 30 --force-refresh
```

## API server usage

```bash
uvicorn app.main:app --reload
```

POST `http://127.0.0.1:8000/extract` with JSON:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "en",
  "force_refresh": false,
  "min_speaker_seconds": 30.0
}
```

## Testing

```bash
pytest
```
