# GitHub Copilot Instructions

## Context-Mode Mandatory Routing

context-mode MCP tools are mandatory for context protection. Follow these rules to avoid flooding the context window.

### Think In Code (Mandatory)

When you need to analyze, count, filter, compare, search, parse, or transform data:

- Use `ctx_execute(language, code)` or `ctx_execute_file(path, language, code)`.
- Program the analysis and print only the final answer.
- Prefer pure JavaScript with Node.js built-ins (`fs`, `path`, `child_process`) for data processing.
- Use `try/catch` and null-safe handling.

### Blocked Flows

Do not retry blocked routes. Use the approved alternatives.

- Terminal `curl`/`wget` -> use `ctx_fetch_and_index(url, source)` or `ctx_execute(...)` with sandboxed fetch.
- Inline HTTP (`fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, `http.request(`) -> use `ctx_execute(...)`.
- WebFetch/fetch tools for web research -> use `ctx_fetch_and_index(...)` then `ctx_search(...)`.

### Redirected Flows

- Terminal commands that may produce large output (>20 lines): use `ctx_batch_execute(...)` or `ctx_execute(language: "shell", code: "...")`.
- Keep terminal for operational commands such as `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`.
- `read_file` for analysis is disallowed. Use `ctx_execute_file(...)`.
- `read_file` is allowed when reading files you will edit.

### Tool Selection Order

1. Memory resume: `ctx_search(sort: "timeline")`.
2. Gather: `ctx_batch_execute(commands, queries)`.
3. Follow-up: `ctx_search(queries: [...])`.
4. Processing: `ctx_execute(...)` or `ctx_execute_file(...)`.
5. Web: `ctx_fetch_and_index(...)` then `ctx_search(...)`.
6. Indexing docs: `ctx_index(content|path, source)`.

### Parallel I/O Rule

- Use `concurrency: 4-8` for I/O-bound multi-request batches.
- Use `concurrency: 1` for CPU-bound tasks (tests/build/lint) or stateful operations.

### Output Policy

- Write artifacts to files, never inline long artifacts.
- Return artifact path plus one-line description.

### Session Continuity

- Keep active skills, roles, and decisions for the full session unless explicitly changed.
- On resume, search memory first before asking what was in progress.

### Context Commands

- `ctx stats` -> call stats tool and show full output verbatim.
- `ctx doctor` -> call doctor tool, run returned command, show checklist output.
- `ctx upgrade` -> call upgrade tool, run returned command, show checklist output.
- `ctx purge` -> call purge with `confirm: true` and warn it is irreversible.

After `/clear` or `/compact`, context-mode knowledge base is preserved. Use `ctx purge` to start fresh.

## Project Scope

Repo automate trending music video pipeline: fetch trending YouTube music data, score candidates, generate horizontal+vertical videos, publish, update Spotify state.

## Operating Mode

Treat repo as migration toward stricter hexagonal architecture.

- New code follow target architecture + canonical imports.
- Legacy modules + shims may exist during migration.
- Do not extend legacy patterns because they exist.
- When existing code conflict rules, preserve behavior + migrate incrementally unless user ask bigger refactor.

## Architecture Guardrails

Target layout:

- domain: business rules + canonical models
- application: use cases + orchestration against ports
- adapters: one adapter per integration implementing protocols
- infrastructure: repositories, clients, media pipeline, platform-specific systems
- config + shared: settings + cross-cutting utilities
- entrypoints + web: thin delivery layers only

Historical shims src/db_client.py, src/video_processing.py, src/yt_client.py already migrated out of main tree. Do not reintroduce modules or old import paths. Main remaining legacy concentration in src/web/main.py + few orchestration flows pending decomposition.

Canonical domain port names: TrendingVideoFetcher, TimeSeriesReader, VideoMetadataReader, AuthCredentialStore, ReleaseDateValidator, VideoPublisher, OAuthProvider[OAuthResultT]. Do not introduce compat aliases or infra-flavored port names in new domain code.

## Layer Rules

Rules normative for new code + any code being refactored.

- domain import only Python stdlib + pydantic.
- domain/services import only domain models + domain exceptions.
- application import domain + protocols from src.domain.ports.
- adapters import domain + only infrastructure clients strictly needed for that adapter.
- infrastructure import domain models + external libs, never application.
- entrypoints wire application + config only. No new business logic.
- web delegate to application use cases. No scoring, ranking, publishing, repository orchestration.
- No cross-layer imports bypass boundaries.
- Domain protocols structural only. No @runtime_checkable, runtime isinstance checks, module-level protocol assertions. Protocol compliance tests: prefer structural assignment checks; use mocks/fakes for behavior tests.

## Boundary Types

Only canonical models cross layer boundaries.

Allowed cross-layer types:

- CanonicalVideo
- PublishingResult
- FetchTrendingRequest
- FetchTrendingResult
- PublishVideoRequest
- PublishVideoResult
- YtAuth
- TikTokAuth
- SpotifyAuth

Adapters translate external payloads into canonical models before return.
No leak raw API dicts, SDK objects, response models, transport-specific data outside adapters/infrastructure.

## New Code Rules

- Use src.config.settings.get_app_settings for settings access.
- Use src.shared.logging.get_logger for app logging.
- Never bare print for runtime logging.
- No import deprecated shim modules in new code.
- No module-level protocol assertions like assert isinstance(MyPublisher(), VideoPublisher).
- No mutable default args.
- No Pydantic v1 code.
- Keep validation at boundaries, not deep in business logic.

## Async and Publishing Rules

- Use async + await for HTTP, storage, filesystem, publish ops when underlying API supports.
- Use asyncio.TaskGroup for concurrent publishing + fan-out workflows.
- Handle per-platform failures explicitly so one publish failure not abort full reporting flow, unless use case require fail-fast.
- No blocking I/O inside async flows without isolating.
- Publishing flows check publication state through domain port, not concrete infra types.
- Detailed async/task orchestration examples belong in `python-async-patterns` + `hexagonal-architecture-video-publish`.

## Platform Integration Rules

Adding new publishing platform:

1. Create src/adapters/{platform}_publisher.py.
2. Implement VideoPublisher protocol from src/domain/ports.py.
3. Add protocol compliance coverage in tests/unit/adapters/test_protocol_compliance.py.
4. Register adapter in src/infrastructure/publisher_registry.py.
5. No change domain or use-case contracts unless business capability changes.
- Keep detailed platform patterns in `hexagonal-architecture-video-publish`.

## Python Rules

- Follow project runtime in pyproject.toml. Prefer modern Python syntax + stdlib features available there.
- Fully type public functions, methods, class attributes.
- Prefer X | None over Optional[X].
- Avoid Any unless clear justified boundary reason.
- Use Pydantic v2 APIs like model_dump + model_validate.
- Prefer frozen models for canonical boundary types when mutation not required.

## Testing Rules

- Write tests before or alongside implementation. Adding new behavior include test in same change. No change observable behavior without corresponding test.
- Unit tests: tests/unit/{layer}/test_{module}.py.
- Integration tests: tests/integration/{layer}/.
- E2E tests: tests/e2e/.
- Mock external deps in unit tests.
- Keep test-tool specifics (tmp_path, respx, slow markers) in dedicated testing skills.
- No pytest.mark.skip to hide failing tests; fix or remove.

## Delivery and Media Rules

- Preserve ffmpeg, ImageMagick, font, file-path assumptions unless task is migration.
- Keep rendering + transcoding logic inside infrastructure/video.
- No mix business ranking logic with media rendering code.
- Keep FastAPI route handlers thin.
- Validate inbound data at boundary.
- Delegate business actions to application use cases.
- No React or Vue unless user ask.

## Secrets and Configuration

- Never commit credentials, tokens, cookies, session files, OAuth artifacts.
- Keep secrets out of source, fixtures, examples, logs.
- Use env vars + git-ignored .env files for local config.

## Anti-Patterns

No code that does:

- Module-level assert isinstance protocol checks.
- New imports from src.db_client, src.logger, src.settings.
- Raw dict payloads crossing architectural boundaries.
- Bare print for application logging.
- Mutable default args.
- Pydantic v1 APIs.
- Blocking I/O inside async code.
- New business logic inside entrypoints, web routes, low-level infra clients.

## Documentation Scope

- Keep this file focused on repo-wide architecture, layering, anti-patterns, migration rules, quality gates.
- Keep path-specific rules in .github/instructions/*.instructions.md when specialization needed.
- Keep operational defaults + command shortcuts in .github/copilot-settings.md.

## Multi-Agent Orchestration

- Use `Solution Architect` custom agent as analysis orchestrator only.
- Delegate specialist analysis to `CTO`, `DBA`, `Design`; synthesize one recommendation with explicit trade-offs.
- Apply least privilege by default:
- `CTO` + `DBA` read-only analysis agents.
- `Design` edit frontend-facing surfaces only.
- Keep agent recommendations aligned with architecture guardrails in this file + path-specific instructions.

## Definition of Done

Change not complete unless all true:

- Architecture boundaries respected.
- New code uses canonical imports.
- Tests added or updated when behavior changed.
- Formatting, lint, type checking, relevant tests run or reason stated explicitly.
- No secrets or generated auth artifacts introduced.

## Proof of Work (Mandatory)

For every code change, always provide a concise Proof of Work block in the final response.

Required PoW contents:

- Commands executed.
- Tests executed.
- Pass/fail counts.
- Validated user-facing flows.
- Non-validated flows (if any), with explicit reason.

Minimum validation by change type:

- Backend/API route changes: success path test, validation/error path test, auth/permission test, and relevant unit test file run.
- Web/HTMX visual changes: fragment rendering assertions (target id/expected labels/status text), plus relevant web unit test file run.
- Cross-layer behavior changes: run all relevant unit tests for impacted layers and state any remaining gaps.

Do not mark work as complete without PoW unless blocked by environment constraints; if blocked, state the blocker and provide a nearest viable alternative check.

## Skill Routing

Load relevant skill from .github/skills when task matches:

- tinyflux-time-series for TinyFlux schema, queries, aggregations.
- python-async-patterns for async use cases, adapters, TaskGroup workflows.
- python-fastapi-patterns for FastAPI routes, dependencies, request validation.
- jinja2-atomic-design for templates + HTMX fragments.
- python-typing-patterns for protocols, type vars, advanced typing.
- uv-package-manager for dependency + environment changes.
- docker-best-practices for Dockerfile or entrypoint changes.
- hexagonal-architecture-video-publish for new VideoPublisher adapters.
- video-processing-migration for media pipeline migrations.
- python-observability-patterns for structured logging with structlog, logger setup, log event formatting.
- python-resilience-patterns for retry logic, aiohttp session management, timeout configuration.
- python-testing-respx for mocking outbound HTTP in tests with respx + create_autospec patterns.
