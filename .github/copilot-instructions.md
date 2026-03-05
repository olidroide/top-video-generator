# GitHub Copilot Instructions

## Project Summary

Automated pipeline: fetch daily/weekly top YouTube music → score/rank → generate video (horizontal + vertical) → publish to YouTube/Instagram/TikTok → update Spotify playlist.

- Backend: FastAPI + Jinja2 SSR (HTMX, no React/Vue)
- Storage: TinyFlux (timeseries) + TinyDB (metadata/auth tokens)
- Media: yt-dlp + moviepy + ffmpeg + ImageMagick + Pillow

---

## Architecture: Hexagonal (Ports & Adapters) — Phase 4 State

### Canonical Directory Layout

```
src/
├── domain/                        # Pure Python — ONLY stdlib + pydantic allowed
│   ├── models.py                  # CanonicalVideo, Video, Release, VideoPoint, auth models
│   ├── ports.py                   # VideoDataSource, VideoPublisher (typing.Protocol)
│   ├── exceptions.py              # DomainError, FetchError, PublishError, ScoringError
│   └── services/
│       └── scoring_service.py     # score_and_rank(), calculate_views_growth() — pure functions
│
├── application/                   # Use Cases — orchestrate domain + ports
│   ├── fetch_trending_use_case.py # FetchTrendingUseCase
│   ├── publish_video_use_case.py  # PublishVideoUseCase (asyncio.TaskGroup)
│   ├── score_videos_use_case.py   # ScoreVideosUseCase
│   └── workers/                   # Background task orchestrators
│
├── adapters/                      # One file per integration, implements Protocols
│   ├── youtube_source.py          # implements VideoDataSource
│   ├── youtube_publisher.py       # implements VideoPublisher
│   ├── tiktok_publisher.py        # implements VideoPublisher
│   └── instagram_publisher.py     # implements VideoPublisher
│
├── infrastructure/                # Concrete implementations, external systems
│   ├── publisher_registry.py      # build_publishers() factory
│   ├── storage/
│   │   ├── video_repository.py    # TinyDB: VideoRecord CRUD
│   │   ├── timeseries_repository.py # TinyFlux: VideoPoint time-series
│   │   ├── auth_repository.py     # TinyDB: SpotifyAuth, TikTokAuth, YtAuth
│   │   └── release_repository.py  # TinyDB: Release tracking / idempotency
│   ├── video/                     # Media pipeline (C1 split in progress)
│   │   └── __init__.py            # Placeholder — video_processing.py pending migration
│   ├── youtube/                   # ⚠️ C3 PENDING — yt_client.py migration
│   │   ├── api_client.py          # YouTube Data API v3 calls
│   │   ├── auth_manager.py        # OAuth2 flow, token refresh
│   │   └── uploader.py            # upload_video, playlist management
│   └── social/                    # Platform API clients
│       ├── instagram_client.py
│       ├── spotify_client.py
│       └── tiktok_client.py
│
├── config/
│   └── settings.py                # Pydantic v2 AppSettings — use get_app_settings()
│
├── shared/
│   └── logging.py                 # get_logger() — use structlog, never bare print
│
├── entrypoints/                   # CLI wrappers only — NO business logic here
│   ├── fetch_data.py
│   ├── publish_video.py
│   └── publish_vertical.py
│
└── web/                           # FastAPI app
    ├── main.py
    ├── templates/
    └── static/

# LEGACY — shims only, DO NOT add new code here:
# src/db_client.py       → shim → infrastructure/storage/
# src/logger.py          → shim → shared/logging.py
# src/settings.py        → shim → config/settings.py
# src/video_processing.py → PENDING migration to infrastructure/video/
# src/yt_client.py        → PENDING migration to infrastructure/youtube/
```

---

## Layer Dependency Rules (non-negotiable)

- `domain/` imports: **only stdlib + pydantic**. Zero `src.*` imports.
- `domain/services/` imports: only from `domain/models.py` and `domain/exceptions.py`.
- `adapters/` imports: `domain/` + one specific infrastructure client. Never cross-adapter imports.
- `application/` imports: `domain/` + `adapters/` via Protocols. Never direct infrastructure imports.
- `infrastructure/` imports: `domain/models.py` + external libraries. No `application/` imports.
- `entrypoints/` imports: `application/` and `config/` only. They wire, never compute.
- `web/` imports: `application/` use cases only. Never direct domain or infrastructure imports.

---

## Protocols — How to Add a New Platform

1. Create `src/adapters/{platform}_publisher.py` implementing `VideoPublisher` Protocol.
2. **DO NOT** add `assert isinstance(...)` at module level — use tests instead.
3. Add a test in `tests/unit/adapters/test_protocol_compliance.py`:
   ```python
   def test_{platform}_publisher_implements_protocol() -> None:
       from src.adapters.{platform}_publisher import MyPublisher
       mock = create_autospec(MyPublisher, instance=True)
       assert isinstance(mock, VideoPublisher)
   ```
4. Register in `src/infrastructure/publisher_registry.py` → `build_publishers()`.
5. Zero changes required in scripts, domain, or application layer.

---

## Canonical Models — Cross-Layer Boundary Types

Only these types may cross layer boundaries:
- `CanonicalVideo` (frozen Pydantic model) — video data flowing through the pipeline
- `PublishingResult` (frozen Pydantic model) — result of a publish operation
- `FetchTrendingRequest/Result`, `PublishVideoRequest/Result` — Use Case DTOs

Adapters MUST translate platform API responses into canonical types before returning.
Scripts/entrypoints MUST NEVER handle raw dicts or platform-specific objects.

---

## Concurrent Publishing

Use `asyncio.TaskGroup` for parallel publishing. Failure on one platform must never block others:

```python
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(_publish_one(p)) for p in self._publishers]
results = [t.result() for t in tasks]
```

---

## Settings Access

```python
# CORRECT
from src.config.settings import get_app_settings
settings = get_app_settings()

# DEPRECATED (shim still works but don't use in new code)
from src.settings import get_app_settings
```

---

## Logging

```python
# CORRECT
from src.shared.logging import get_logger
logger = get_logger(__name__)

# DEPRECATED (shim still works but don't use in new code)
from src.logger import get_logger
```

---

## Idempotency Guard

Every entrypoint that publishes MUST check before running. **Do not** invent your own pattern — use this exactly:

```python
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.domain.models import ReleasePlatform
from datetime import date

async def _already_published_today(repo: ReleaseRepository, day: date) -> bool:
    """Check if video was already released to all platforms on this date."""
    return all(
        repo.is_release_at_date(platform=p.value, day=day)
        for p in ReleasePlatform
    )

# In entrypoint (e.g., PublishVideoUseCase.execute):
async def execute(self, day: date) -> None:
    if await _already_published_today(self._release_repo, day):
        logger.info("already_published", day=str(day))
        return
    # ... proceed with publish pipeline
```

---

## Testing Conventions

- Unit tests: `tests/unit/{layer}/test_{module}.py` — mock all external deps
- Integration tests: `tests/integration/{layer}/` — use `tmp_path` fixture for TinyDB/TinyFlux
- E2E: `tests/e2e/` — full pipeline with mocked HTTP (respx)
- **Never** use `pytest.mark.skip` to suppress failing tests — fix or delete them
- Test files that exercise media pipeline (moviepy/ffmpeg) go in `tests/integration/video/` with `@pytest.mark.slow`

---

## What NOT to do (active anti-patterns being removed)

- ❌ `assert isinstance(MyClass(), SomeProtocol)` at module level — use `create_autospec` in tests
- ❌ `from src.db_client import DatabaseClient` — use specific repository classes
- ❌ `from src.logger import get_logger` — use `src.shared.logging`
- ❌ `from src.settings import get_app_settings` — use `src.config.settings`
- ❌ Mutable default arguments: `def f(day=date.today())` — use `day: date | None = None`
- ❌ Pydantic v1 sts

Load the relevant skill per task. All skills are available in `.github/skills/`:

| Task | Skill | When to load |
|------|-------|-------------|
| Write timeseries queries (TinyFlux) | `tinyflux-time-series` | Building VideoPoint aggregations, time ranges |
| Write async Use Cases / adapters | `python-async-patterns` | PublishVideoUseCase, FetchTrendingUseCase, adapters with asyncio.TaskGroup |
| Add FastAPI routes / dependencies | `python-fastapi-patterns` | New endpoints in src/web/main.py, Pydantic request models |
| Create Jinja2 templates | `jinja2-atomic-design` | New .html templates, HTMX components |
| Define Protocols or TypeVars | `python-typing-patterns` | domain/ports.py (VideoDataSource, VideoPublisher), generics |
| Add/update dependencies | `uv-package-manager` | Modify pyproject.toml, manage virtual environments |
| Edit Dockerfile or entrypoint | `docker-best-practices` | Docker build optimization, multi-stage, secrets |
| Add a new VideoPublisher adapter | `hexagonal-architecture-video-publish` | New platform publishing (TikTok, YouTube, etc) |
| Handle video processing migration | `video-processing-migration` | C1 split (infrastructure/video), media pipeline refactoring |
---

## Tooling

- Package manager: `uv` (never pip)
- Format: `ruff format`
- Lint: `ruff check`
- Type check: `ty`
- Tests: `pytest` (asyncio_mode = "auto")

---

## Skill Reference

For detailed patterns and templates, load skill: `hexagonal-architecture-video-publish`
