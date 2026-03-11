---
name: uv-package-manager
description: Master the uv package manager. Triggers on: pyproject.toml, uv.lock, dependency management, pip alternatives, Dockerfile with Python, CI/CD Python setup, venv, requirements.txt migration.
compatibility: uv 0.4.x+
---

# UV Package Manager

## Core Directives

- **Always use `uv` instead of `pip`, `poetry`, or `pip-tools`** for all Python dependency management.
- **Never activate venvs manually** (`source .venv/bin/activate`); use `uv run <command>`.
- **Never generate `requirements.txt`** unless specifically requested for a legacy system. Rely on `pyproject.toml` and `uv.lock`.

## Daily Developer Workflows

### Project Initialization & Python Version

```bash
uv init .              # Initialize in current directory
uv python pin 3.12     # Pin Python version (.python-version)
```

### Adding/Removing Dependencies

```bash
uv add fastapi pydantic         # Add to dependencies
uv add --dev pytest ruff        # Add to dev-dependencies
uv remove pandas                # Remove dependency
```

### Execution (Zero-friction venv)

```bash
uv run python src/main.py
uv run pytest tests/
uv run ruff check src/
```

## Production & CI/CD Patterns

### Lockfile Management

```bash
uv lock                         # Generate/update uv.lock
uv lock --upgrade-package httpx # Upgrade specific package
```

### CI/CD Setup (GitHub Actions)

```yaml
steps:
  - uses: actions/checkout@v4
  - name: Install uv
    uses: astral-sh/setup-uv@v2
    with:
      enable-cache: true
      cache-dependency-glob: "uv.lock"
  - name: Install dependencies
    run: uv sync --all-extras --dev
  - name: Run tests
    run: uv run pytest
```

## Docker Best Practices (Multi-Stage)

**MANDATORY**: Always use cache mounts and isolate dependency installation from code copying to maximize Docker layer caching.

```dockerfile
# BUILDER STAGE
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Optimizations for Docker mounts
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1. Install dependencies FIRST (layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

# 2. Copy code and install project
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# RUNTIME STAGE
FROM python:3.12-slim AS runtime
WORKDIR /app

# Copy the isolated venv
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "src.main"]
```

## Anti-Patterns to Correct

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| `pip install -r requirements.txt` | `uv sync` |
| `python -m venv .venv && source .venv/bin/activate` | `uv sync` (creates venv automatically) |
| `uv pip install ...` inside a Dockerfile | `uv sync --frozen` |
| `COPY . .` before `uv sync` in Docker | Sync lockfiles first, copy code later |
