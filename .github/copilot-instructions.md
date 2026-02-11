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
