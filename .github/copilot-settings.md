# Copilot Settings

## Fast Defaults

- pre-commit: uv run pre-commit run --all-files
- test: uv run pytest
- lint: uv run ruff check src/ tests/
- format: uv run ruff format src/ tests/
- typecheck: uv run ty check src/
- quality: make quality
- run: uv run {script}

## Local Enforcement

- Install pre-commit managed hooks once per clone: make install-hooks
- Pre-commit runs fast staged-file checks: file hygiene, secrets, ruff fix, and ruff format.
- Ruff hooks run only at the pre-commit stage.
- Pre-push runs through pre-commit and enforces the heavy repository gate: make quality plus the main pytest suite.

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
