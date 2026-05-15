# Project rules — CI checks

MANDATORY before every commit. CI fails if any step fails.

## Order of execution

```bash
# 1. Format
uv run ruff format --check src/ tests/

# 2. Lint
uv run ruff check src/ tests/

# 3. Type check
uv run ty check src/ tests/

# 4. Tests
uv run pytest tests/ -x -q --ignore=tests/integration/video

# 5. Pre-commit
uv run pre-commit run --hook-stage pre-commit --all-files

# 6. Pre-push
uv run pre-commit run --hook-stage pre-push --all-files
```

## Shortcuts

- `make quality` = ruff format --check + ruff check + ty check
- `make test` = pytest same flags as CI
- `make pre-commit-run` = pre-commit pre-commit stage
- `make pre-push-check` = pre-commit pre-push stage

## Rules

- NEVER commit without running all 6 checks
- If any check fails, fix and re-run ALL checks
- HTML templates (*.html) excluded from ruff (Jinja2 syntax)
- Tests in `tests/unit/` and `tests/integration/`
- Integration video tests excluded from CI (`--ignore=tests/integration/video`)
