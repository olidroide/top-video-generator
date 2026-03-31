# top-video-generator

Generate automatically a video resume with the most view growing in a weekly/daily basis.

## Architecture Overview

This application fetches daily/weekly top YouTube music videos for a configured region (currently Bollywood/India), stores timeseries data and metadata, generates videos (horizontal and vertical formats), and publishes to YouTube, Instagram, TikTok, and Spotify playlists.

### System Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Fetch    │────▶│  Video Processing │────▶│    Publishing   │
│  (YouTube API)  │     │  (moviepy/ffmpeg) │     │ (YT/IG/TT/Spot)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                          │
         ▼                       ▼                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   TinyFlux      │     │   Templates      │     │   Platform      │
│  (Timeseries)   │     │   & Assets       │     │   Clients       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│    TinyDB       │
│   (Metadata)    │
└─────────────────┘
```

### Key Components

#### 1. Data Ingestion (`src/script_fetch_yt_data.py`)
- Scheduled daily fetch from YouTube API
- Stores video metadata and view counts
- Calculates view growth and rankings
- Writes to TinyFlux (timeseries) and TinyDB (metadata)

#### 2. Video Processing Pipeline
- **Downloader** (`src/video_downloader.py`): Uses yt-dlp to fetch source videos
- **Processing** (`src/video_processing.py`): Composites templates, overlays, transitions using moviepy
- **Workers** (`src/worker_post_process_video.py`): ZeroMQ-based parallel processing

#### 3. Publishing Scripts
- **Daily Vertical** (`src/script_generate_vertical_publish_top_video.py`): Top 5 videos, vertical format for Reels/Shorts
- **Weekly Horizontal** (`src/script_generate_publish_top_video.py`): Top videos, horizontal format for YouTube

#### 4. Platform Clients
- **YouTube** (`src/yt_client.py`): OAuth2, video upload, playlist management
- **TikTok** (`src/tiktok_client.py`): OAuth2, video upload with chunked transfer
- **Spotify** (`src/spotify_client.py`): OAuth2, playlist management
- **Instagram** (`src/instagram_client.py`): Session-based auth via instagrapi

#### 5. Web Interface (`src/web/main.py`)
- FastAPI + Jinja2 SSR
- OAuth callback handlers for all platforms
- Video ranking viewer with date navigation
- Background task triggers

### Technology Stack

- **Backend**: Python 3.14+, FastAPI, Pydantic
- **Video**: moviepy, yt-dlp, ffmpeg, PIL
- **Storage**: TinyFlux (timeseries CSV), TinyDB (JSON)
- **Web**: Jinja2 templates, HTMX-ready
- **Deployment**: Docker, Docker Compose
- **Package Management**: uv (ultrafast Python package manager)

### Configuration

All configuration is via environment variables with `TOP_MUSIC_` prefix:

```bash
# Core settings
TOP_MUSIC_ENV=production|development
TOP_MUSIC_DAYS_BETWEEN_TOP=7

# YouTube API
TOP_MUSIC_YT_CLIENT_SECRET_FILE=yt_client_secret.json
TOP_MUSIC_YT_SEARCH_REGION_CODE=IN
TOP_MUSIC_YT_SEARCH_LANGUAGE_CODE=hi

# Platform credentials (see src/.env.example)
```

### Current Architecture Issues

1. **Blocking Operations in Async Code**: `googleapiclient` and `instagrapi` are synchronous libraries called from async contexts without executor isolation, risking event loop blocking.

2. **Monolithic Deployment**: Single container handles all concerns (fetch, process, publish, web) via STEP env var, limiting scalability.

3. **Local Storage**: TinyDB/TinyFlux work for single-instance but lack concurrency controls and backup mechanisms.

4. **Limited Observability**: No health checks, metrics, or centralized logging correlation IDs.

5. **Error Handling**: Uploads lack retry with exponential backoff; failures are logged but not queued for retry.

### Improvements Implemented

✅ **Async Adapters** (`src/adapters/`): Wrap blocking clients in `run_in_executor()`
✅ **Retry Utilities** (`src/utils/retry.py`): Exponential backoff with jitter for resilient uploads
✅ **Health Checks** (`/health` endpoint): Validates ffmpeg, templates, database
✅ **Metrics** (`/metrics` endpoint): Tracks fetch/upload/processing counts and errors
✅ **CI/CD** (`.github/workflows/ci.yml`): Automated testing, linting, type checking

### Planned Improvements

- [ ] Message broker (Redis/RabbitMQ) for reliable task queuing
- [ ] Separate container services for ingest/process/publish
- [ ] Migrate from TinyDB to PostgreSQL for metadata
- [ ] Add Prometheus metrics export
- [ ] Implement dead-letter queue for failed uploads
- [ ] Add integration tests with mocked external APIs

## Quick Start

### Prerequisites

- Python 3.14+
- ffmpeg installed
- Docker (optional)

### Local Development

```bash
# Install dependencies with uv
uv pip install -e ".[dev]"

# Run web server
uvicorn src.web.main:app --reload --port 8080

# Run data fetch
STEP=fetch_data python src/script_fetch_yt_data.py

# Run daily publish
STEP=vertical_publish python src/script_generate_vertical_publish_top_video.py
```

### Docker

```bash
# Build and run
docker-compose up --build

# Run specific step
docker-compose run --rm top-video-generator STEP=fetch_data
```

## License

MIT
