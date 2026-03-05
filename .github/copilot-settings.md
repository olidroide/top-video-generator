# Copilot Settings

## Preferred Tools (enforced)

- **test**: `uv run pytest`
- **lint**: `uv run ruff check src/ tests/`
- **format**: `uv run ruff format src/ tests/`
- **typecheck**: `uv run ty check src/`
- **run**: `uv run {script}`

## Dependency Management

- Use `uv` for installs and venv creation, **never pip directly**.
- Preferred commands:
  - `uv sync --all-extras` (dev + test dependencies)
  - `uv sync --no-dev --frozen` (locked prod dependencies)
- Do not use pip directly in Makefile or Dockerfile.

## Code Style

- **Python 3.12+** features allowed (match-case, type union syntax `X | None`).
- **Type hints**: strict, all parameters and return types annotated.
- **Async-first**: all I/O operations (database, HTTP, file) use async/await.
- **Pydantic v2**: use `.model_dump()` and `.model_validate()` (NOT `.dict()` or `.parse_obj()`).
- **Structlog**: all logging via `get_logger(__name__)`, never bare `print`.

## Docker Build

- Builder stage installs dependencies with `uv`.
- Keep `/opt/venv` pattern and copy into runtime stage.
- Runtime stage: `FROM python:3.12-slim`, copy venv, set `PYTHONUNBUFFERED=1`.

## Secrets & Configuration

- Never commit credentials, session files, or API tokens.
- Use `src/.env` (git-ignored) and environment variables for config.
- Access settings via `from src.config.settings import get_app_settings()`.

## Conventional Commits

- **Format**: `type(scope): description`
- **Types**: `feat`, `fix`, `refactor`, `test`, `chore`
- **Examples**:
  - `feat(storage): add video_repository for TinyDB CRUD`
  - `fix(publishers): handle asyncio.TaskGroup cancellation`
  - `refactor(domain): consolidate VideoPoint model inheritance`
  - `test(adapters): add protocol compliance tests`

## Linting & Type Checking (Pre-commit)

These must pass before commit:
- `ruff format --check src/`
- `ruff check src/ tests/` (no F401 unused imports, E501 line length, etc.)
- `ty check src/` (strict type checking, no `Any` unless justified)
