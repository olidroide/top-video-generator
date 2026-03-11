# Copilot Settings

## Fast Defaults

- test: uv run pytest
- lint: uv run ruff check src/ tests/
- format: uv run ruff format src/ tests/
- typecheck: uv run ty check src/
- run scripts: uv run {script}

## Dependency Defaults

- Use uv for installs, sync, and virtual environments.
- Never use pip directly in docs, scripts, Makefile targets, CI, or Dockerfiles.
- Preferred sync commands: uv sync --all-extras, uv sync --no-dev --frozen

## Finish Checks

Run these before finishing a change when relevant:

- uv run ruff format src/ tests/
- uv run ruff check src/ tests/
- uv run ty check src/
- uv run pytest
