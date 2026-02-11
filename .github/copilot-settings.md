# Copilot Settings

## Dependency Management

- Use uv for installs and venv creation.
- Preferred commands:
  - uv sync --all-extras
  - uv sync --no-dev --frozen
- Do not use pip directly in Makefile or Dockerfile.

## Docker Build

- Builder stage should install dependencies with uv.
- Keep the /opt/venv venv pattern and copy it into the runtime stage.

## Code Style

- Python 3.11+ features are allowed.
- Use ruff format for formatting and ruff check for linting.
- Use ty for type checking.
- Preserve existing async patterns and structlog usage.

## Secrets

- Never commit credentials, session files, or tokens.
- Use src/.env and environment variables for config.
