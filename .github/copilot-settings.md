# Copilot Settings

## Fast Defaults

- test: uv run pytest
- lint: uv run ruff check src/ tests/
- format: uv run ruff format src/ tests/
- typecheck: uv run ty check src/
- quality: make quality
- run: uv run {script}

## Local Enforcement

- Install tracked git hooks once per clone: make install-hooks
- Pre-push hook runs full-repository quality checks via make quality.

## Dependency Defaults

- Use uv for installs, sync, lockfile management, and virtual environments.
- Never use pip directly in docs, scripts, Makefile targets, CI, or Dockerfiles.
- Preferred sync commands: uv sync --all-extras, uv sync --no-dev --frozen

## Scope

- Keep this file operational and concise.
- Architecture, layering, anti-patterns, and migration rules belong in .github/copilot-instructions.md.

## Finish Checks

Run these before finishing a change unless the task is documentation-only or explicitly exempted:

- uv run ruff format src/ tests/
- uv run ruff check --fix src/ tests/
- uv run ty check src/
- uv run pytest
