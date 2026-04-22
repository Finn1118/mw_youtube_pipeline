# mw_youtube_pipeline

FastAPI service and Python library that take a **YouTube URL** and return **diarized speakers** with **concatenated spoken text**, plus video metadata. Intended for workflows where a human confirms identities before creating people or profiles downstream.

---

### Note for reviewers

This repository is the **standalone extraction service** referenced from local platform development. It is **not** wired to production auth or hosting yet. Please use this README and `.env.example` as the source of truth for behavior, configuration, and deployment considerations. Suggestions on cache storage (SQLite today), job/async shape, and whether this stays Python on Cloud Run versus a TypeScript port are welcome.

---

## What it does

1. **Resolve** the video ID from the URL and check a **SQLite** cache (keyed by video, language, and minimum speaking-time thresholds).
2. **Fetch audio** with **yt-dlp** when needed (skips download if cached utterances can be reused).
3. **Transcribe** with **Deepgram** (Nova-3, diarization + utterances).
4. **Name speakers** with an **OpenAI** model using structured outputs from a text brief (title, channel, description, diarized snippet, per-speaker stats and sample lines). Weak mappings may trigger a retry with a stronger model.
5. **Aggregate** utterances per diarization speaker ID, drop speakers below a configurable minimum speaking time, sort by speaking time, and return an **ExtractionResult** (and persist to SQLite for repeat requests).

Private, deleted, or region-blocked videos surface as clear errors rather than partial data.

## Requirements

- **Python 3.11+**
- **ffmpeg** on `PATH` (used by yt-dlp for audio extraction where applicable)
- **Deno** (required by current **yt-dlp** for YouTube JS challenges)

## Environment

Copy `.env.example` to `.env` and fill in values. **Never commit `.env`** — it is listed in `.gitignore`.

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPGRAM_API_KEY` | Yes | Deepgram API key for transcription. |
| `OPENAI_API_KEY` | Yes | OpenAI API key for speaker identification. |
| `SPEAKER_CACHE_PATH` | No | SQLite cache path (default: `./.speaker_cache.sqlite`). |

## Install

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
```

Optional: `pip install -e ".[dev]"` from the repo root for pytest extras declared in `pyproject.toml`.

## CLI

```bash
python -m speaker_extraction "https://www.youtube.com/watch?v=VIDEO_ID"
```

Useful flags: `--language en`, `--min-seconds 30`, `--force-refresh`.

## HTTP API (local)

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/extract` | Run pipeline (or cache hit); body matches `ExtractionRequest` (JSON: `url`, `language`, `force_refresh`, `min_speaker_seconds`, etc.). |
| `GET` | `/library` | List cached videos with speaker summaries. |
| `PATCH` | `/library/{video_id}/speakers` | Update cached speaker display names after user edits. |

CORS is restricted to **Vite’s default dev origin** (`localhost` / `127.0.0.1` on port **5173**) for local UI integration. Production should use **server-to-server** calls and tight CORS or no browser CORS at all.

A small static UI is mounted at `/` for manual testing.

## Testing

```bash
pytest
```

## Project layout

| Path | Role |
|------|------|
| `speaker_extraction/` | Core pipeline: fetch, transcribe, identify, extract, cache, types, errors. |
| `app/main.py` | FastAPI app, routes, CORS, static `web/` mount. |
| `web/` | Optional static test UI. |
| `tests/` | Pytest suite. |

Package import name remains **`speaker_extraction`** (see `pyproject.toml`).

## Production considerations (draft)

- **Secrets**: Load `DEEPGRAM_API_KEY` and `OPENAI_API_KEY` from a secret manager or platform env; do not expose them to browsers or front-end bundles.
- **Cache**: Replace or supplement file-based SQLite with a managed store (e.g. Cloud SQL, GCS artifacts + metadata) if multiple instances run.
- **Long requests**: Full runs can exceed comfortable HTTP timeouts; an **async job** + status polling (or webhook) may match how the rest of the stack handles heavy work.
- **Hosting**: A **Cloud Run** (or similar) container for this service is a natural fit next to a TypeScript API; rewrites to TypeScript are optional and mainly trade operational simplicity against rewrite cost (especially around yt-dlp).
- **Compliance**: Transcripts and audio may contain sensitive content; retention and logging policies should align with org requirements.

## License / ownership

Proprietary — confirm with Millionways before redistribution.
