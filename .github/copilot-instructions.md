# Copilot Instructions

## Project Summary

- This app fetches daily/weekly top YouTube music videos for a region, stores timeseries and metadata, generates videos (horizontal and vertical), publishes to YouTube/Instagram/TikTok, and updates a Spotify playlist.
- Backend: FastAPI + Jinja2 SSR for the daily top web view.
- Storage: TinyFlux (timeseries) and TinyDB (video metadata/auth tokens).
- Media pipeline: yt-dlp + moviepy + ffmpeg + ImageMagick, with custom fonts in Docker.

## Key Paths

- Core logic: src/
- Web app (SSR): src/web/
- Templates: src/web/templates/
- Static assets: src/web/static/
- Config: src/settings.py reads src/.env
- Database: db/ (TinyFlux CSV + TinyDB JSON)

## Runtime Entry Points

- Data fetch: src/script_fetch_yt_data.py
- Weekly publish (horizontal): src/script_generate_publish_top_video.py
- Daily publish (vertical): src/script_generate_vertical_publish_top_video.py
- Web: src/web/main.py (FastAPI)
- Docker entrypoint: docker-entrypoint.sh (uses STEP env)

## Tooling

- Dependency management: use uv (not pip).
- Formatting: ruff format.
- Linting: ruff.
- Type checking: ty.

## Coding Conventions

- Prefer async I/O for network calls (aiohttp), keep functions async where already used.
- Use structlog via src/logger.py; avoid bare print.
- Keep settings in src/settings.py; access via get_app_settings().
- Avoid leaking secrets: do not hardcode tokens, client secrets, or session files.

## Media/Font Notes

- Docker image installs fonts and sets symlinks used in video_processing.py.
- Keep ffmpeg/ImageMagick assumptions intact when editing video code.

## Testing and Safety

- If changing auth flows or publish steps, keep backward compatibility for stored TinyDB auth records.
- Add minimal validation for user-provided parameters in the web routes.

---

## Foundational Architecture: Hexagonal (Ports & Adapters)

This project follows **Hexagonal Architecture** for all publishing and data-source logic.
Copilot MUST respect these rules in every code change.

### Directory Layout (enforced)

```
src/
├── domain/          # Pure Python — NO external imports allowed here
│   ├── models.py    # CanonicalVideo, PublishingResult (Pydantic, frozen=True)
│   └── ports.py     # VideoDataSource, VideoPublisher (typing.Protocol)
├── adapters/        # One file per external integration
│   ├── youtube_source.py      # Implements VideoDataSource
│   ├── youtube_publisher.py   # Implements VideoPublisher
│   ├── tiktok_publisher.py    # Implements VideoPublisher
│   └── instagram_publisher.py # Implements VideoPublisher
└── infrastructure/
    └── publisher_registry.py  # build_publishers() — reads settings, returns list[VideoPublisher]
```

### Layer Dependency Rules (non-negotiable)

- `domain/` → imports nothing from `src/` (only stdlib + pydantic).
- `adapters/` → imports from `domain/` and the specific external client. Never cross-imports between adapters.
- `infrastructure/` → imports from `adapters/` and `domain/`. Builds the wiring.
- Scripts → import from `infrastructure/` and `domain/` only. They are orchestrators, NOT business logic owners.

### Ports (typing.Protocol)

Use `typing.Protocol` with `@runtime_checkable`. Never use ABC inheritance.

```python
@runtime_checkable
class VideoPublisher(Protocol):
    @property
    def platform_name(self) -> Platform: ...
    @property
    def is_enabled(self) -> bool: ...
    async def publish_video(
        self, video_list: list[CanonicalVideo], file_path: str,
        title: str, description: str,
    ) -> PublishingResult: ...
```

After every new adapter add a structural check:

```python
assert isinstance(MyNewPublisher(), VideoPublisher)  # fails fast at import time
```

### Canonical Models

- `CanonicalVideo` and `PublishingResult` are the **only** types that cross layer boundaries.
- Adapters translate external API responses into canonical models before returning.
- Scripts must NEVER handle raw dicts or platform-specific objects.

### Parallel Publishing (asyncio.TaskGroup)

Publishing to multiple platforms MUST be concurrent, never sequential.
A failure on one platform must never block the others.

### Idempotency Guard

Every publish entry point must check all platforms before running:

```python
if all(db.is_release_at_date(p, day) for p in Platform):
    logger.info("already published today on all platforms")
    return
```

### Adding a New Platform

1. Create `src/adapters/{platform}_publisher.py` implementing `VideoPublisher`.
2. Add `assert isinstance(MyPublisher(), VideoPublisher)` at module level.
3. Register in `src/infrastructure/publisher_registry.py` → `build_publishers()`.
4. Zero changes required in scripts or domain.

### Skill Reference

For detailed patterns and templates, load skill: `hexagonal-architecture-video-publish`
