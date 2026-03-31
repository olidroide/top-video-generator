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

#### 1. Data Ingestion (`src/entrypoints/fetch_data.py`)
- Scheduled daily fetch from YouTube API
- Stores video metadata and view counts
- Calculates view growth and rankings
- Writes to TinyFlux (timeseries) and TinyDB (metadata)

#### 2. Video Processing Pipeline
- **Downloader** (`src/infrastructure/youtube/downloader.py`): Uses yt-dlp to fetch source videos
- **Processing** (`src/infrastructure/video/compositor.py`, `src/infrastructure/video/renderer.py`): Composites templates, overlays, and transitions
- **Workers** (`src/entrypoints/workers/post_processor.py`): ZeroMQ-based parallel processing

#### 3. Publishing Scripts
- **Daily Vertical** (`src/entrypoints/publish_vertical.py`): Top 5 videos, vertical format for Reels/Shorts
- **Weekly Horizontal** (`src/entrypoints/publish_video.py`): Top videos, horizontal format for YouTube

#### 4. Platform Clients
- **YouTube** (`src/infrastructure/youtube/client.py`): OAuth2, video upload, playlist management
- **TikTok** (`src/infrastructure/social/tiktok_client.py`): OAuth2, video upload with chunked transfer
- **Spotify** (`src/infrastructure/social/spotify_client.py`): OAuth2, playlist management
- **Instagram** (`src/infrastructure/social/instagram_client.py`): Session-based auth via instagrapi

#### 5. Web Interface (`src/web/main.py`)
- FastAPI + Jinja2 SSR
- OAuth callback handlers for all platforms
- Video ranking viewer with date navigation
- Background task triggers

### Technology Stack

- **Backend**: Python 3.13, FastAPI, Pydantic
- **Video**: moviepy, yt-dlp, ffmpeg, PIL
- **Storage**: TinyFlux (timeseries CSV), TinyDB (JSON)
- **Web**: Jinja2 templates, HTMX-ready
- **Deployment**: Docker, Docker Compose
- **Package Management**: uv (ultrafast Python package manager)

### Configuration

All configuration is via environment variables with `TOP_MUSIC_` prefix:

```bash
# Copy the example file to the repository root as .env
# and adjust values for your local environment.

# Core settings
TOP_MUSIC_ENV=production|development
TOP_MUSIC_DAYS_BETWEEN_TOP=7

# YouTube API
TOP_MUSIC_YT_CLIENT_SECRET_FILE=yt_client_secret.json
TOP_MUSIC_YT_SEARCH_REGION_CODE=IN
TOP_MUSIC_YT_SEARCH_LANGUAGE_CODE=hi

# Platform credentials (see .env.example)
```

### Current Architecture Issues

1. **Web Delivery Layer Still Dense**: `src/web/main.py` still concentrates routing, dependency wiring, OAuth callbacks, and setup/status endpoints in a single module.

2. **Monolithic Deployment**: A single container still handles fetch, processing, publishing, and web delivery via the `STEP` environment variable.

3. **Local Storage Limits**: TinyDB and TinyFlux remain a good fit for single-instance deployments, but they still lack native concurrency controls and stronger operational tooling.

4. **Process-Local Observability**: `/health` and `/metrics` exist, but metrics are in-memory and local to a single process, not centralized or Prometheus-compatible.

5. **Scoring Logic Duplication**: Ranking behavior exists in the domain scoring service and is still duplicated in some application/entrypoint flows.

### Improvements Implemented

✅ **Hexagonal Split** (`src/domain`, `src/application`, `src/adapters`, `src/infrastructure`): Core migration out of legacy god files is completed
✅ **Async Isolation** (`src/infrastructure/`): Blocking integrations are isolated with `asyncio.to_thread()`
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

- Python 3.13
- ffmpeg installed
- ImageMagick installed
- Docker (optional)

### Local Development

```bash
# Install dependencies and git hooks
make dev-install
make install-hooks

# Run web server
uv run api-server

# Run data fetch
uv run fetch-data

# Run daily publish
uv run publish-vertical

# Run weekly publish
uv run publish-video

# Run quality checks
make quality

# Run the full pre-push gate manually
make pre-push-check
```

### Git Hooks

This repository uses pre-commit as the single hook runner for both commit and push checks.

Run this once per clone:

```bash
make install-hooks
```

What happens after that:

- `git commit` runs the `pre-commit` stage with fast checks for merge conflicts, private keys, whitespace cleanup, `ruff check --fix`, and `ruff format`.
- `git push` runs the `pre-push` stage with the full repository gate: `make quality` plus `pytest tests/ -x -q --ignore=tests/integration/video`.

Important: a commit can pass and a push can still fail. This is expected because `pre-push` runs stricter checks (including `ty check` through `make quality`) that are not part of the fast `pre-commit` stage.

Useful manual commands:

```bash
# Run all pre-commit hooks across the repository
make pre-commit-run

# Run the same checks used by the pre-push hook
make pre-push-check
```

If this clone used the older tracked `.githooks/` setup before, rerun `make install-hooks` to migrate to the native `.git/hooks` installation managed by pre-commit.

### Docker

```bash
# Build and run
docker-compose up --build

# Run specific step
docker-compose run --rm -e "STEP=fetch_data" top-video-generator
```

## License

MIT
