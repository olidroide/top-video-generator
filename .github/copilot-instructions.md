# GitHub Copilot Instructions

## Project Scope

This repository automates the trending music video pipeline: fetch trending YouTube music data, score candidates, generate horizontal and vertical videos, publish them, and update Spotify state.

## Operating Mode

Treat this repository as a migration toward a stricter hexagonal architecture.

- New code must follow the target architecture and canonical imports.
- Legacy modules and shims may still exist while migration completes.
- Do not extend legacy patterns just because they already exist.
- When existing code conflicts with these rules, preserve behavior and migrate incrementally unless the user explicitly asks for a larger refactor.

## Architecture Guardrails

Target layout:

- domain: business rules and canonical models
- application: use cases and orchestration against ports
- adapters: one adapter per integration implementing protocols
- infrastructure: repositories, clients, media pipeline, platform-specific systems
- config and shared: settings and cross-cutting utilities
- entrypoints and web: thin delivery layers only

Historical shims such as src/db_client.py, src/video_processing.py, and src/yt_client.py have already been migrated out of the main tree. Do not reintroduce those modules or their old import paths. The main remaining legacy concentration is in src/web/main.py and a few orchestration flows still pending further decomposition.

Canonical domain port names are TrendingVideoFetcher, TimeSeriesReader, VideoMetadataReader, AuthCredentialStore, ReleaseDateValidator, VideoPublisher, and OAuthProvider[OAuthResultT]. Do not introduce compatibility aliases or infrastructure-flavored port names in new domain code.

## Layer Rules

These rules are normative for new code and for any code being actively refactored.

- domain may import only Python stdlib and pydantic.
- domain/services may import only domain models and domain exceptions.
- application may import domain and protocols from src.domain.ports.
- adapters may import domain and only the infrastructure clients strictly needed for that adapter.
- infrastructure may import domain models and external libraries, but never application.
- entrypoints should only wire application and config. Do not add new business logic there.
- web should delegate to application use cases. Do not add scoring, ranking, publishing, or repository orchestration there.
- Do not add cross-layer imports that bypass these boundaries.
- Domain protocols are structural only. Do not add @runtime_checkable, runtime isinstance checks, or module-level protocol assertions. For protocol compliance tests, prefer structural assignment checks; use mocks/fakes for behavior tests.

## Boundary Types

Only canonical models should cross layer boundaries.

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

Adapters must translate external payloads into canonical models before returning.
Do not leak raw API dictionaries, SDK objects, response models, or transport-specific data outside adapters or infrastructure.

## New Code Rules

- Use src.config.settings.get_app_settings for settings access.
- Use src.shared.logging.get_logger for application logging.
- Never use bare print for runtime logging.
- Do not import deprecated shim modules in new code.
- Do not add module-level protocol assertions such as assert isinstance(MyPublisher(), VideoPublisher).
- Do not use mutable default arguments.
- Do not generate Pydantic v1 code.
- Keep validation at boundaries rather than deep inside business logic.

## Async and Publishing Rules

- Use async and await for HTTP, storage, filesystem, and publish operations when the underlying API supports it.
- Use asyncio.TaskGroup for concurrent publishing and similar fan-out workflows.
- Handle per-platform failures explicitly so one publish failure does not abort the full reporting flow, unless the use case explicitly requires fail-fast semantics.
- Do not introduce blocking I/O inside async flows without isolating it.
- Publishing flows must check publication state through the domain port, not concrete infrastructure types.
- Detailed async/task orchestration examples belong in `python-async-patterns` and `hexagonal-architecture-video-publish`.

## Platform Integration Rules

When adding a new publishing platform:

1. Create src/adapters/{platform}_publisher.py.
2. Implement the VideoPublisher protocol from src/domain/ports.py.
3. Add protocol compliance coverage in tests/unit/adapters/test_protocol_compliance.py.
4. Register the adapter in src/infrastructure/publisher_registry.py.
5. Do not change domain or use-case contracts unless the business capability actually changes.
- Keep detailed platform patterns in `hexagonal-architecture-video-publish`.

## Python Rules

- Follow the project runtime in pyproject.toml. Prefer modern Python syntax and standard library features available there.
- Fully type public functions, methods, and class attributes.
- Prefer X | None over Optional[X].
- Avoid Any unless there is a clear and justified boundary reason.
- Use Pydantic v2 APIs such as model_dump and model_validate.
- Prefer frozen models for canonical boundary types when mutation is not required.

## Testing Rules

- Write tests before or alongside implementation. When adding new behavior, include a test in the same change. Do not change observable behavior without a corresponding test.
- Unit tests live in tests/unit/{layer}/test_{module}.py.
- Integration tests live in tests/integration/{layer}/.
- End-to-end tests live in tests/e2e/.
- Mock external dependencies in unit tests.
- Keep test-tool specifics (e.g. tmp_path, respx, slow markers) in dedicated testing skills.
- Do not use pytest.mark.skip to hide failing tests; fix or remove them.

## Delivery and Media Rules

- Preserve ffmpeg, ImageMagick, font, and file-path assumptions unless the task is explicitly a migration.
- Keep rendering and transcoding logic inside infrastructure/video.
- Do not mix business ranking logic with media rendering code.
- Keep FastAPI route handlers thin.
- Validate inbound data at the boundary.
- Delegate business actions to application use cases.
- Do not introduce React or Vue unless the user explicitly asks for that change.

## Secrets and Configuration

- Never commit credentials, tokens, cookies, session files, or OAuth artifacts.
- Keep secrets out of source code, fixtures, examples, and logs.
- Use environment variables and git-ignored .env files for local configuration.

## Anti-Patterns

Do not generate code that does any of the following:

- Module-level assert isinstance protocol checks.
- New imports from src.db_client, src.logger, or src.settings.
- Raw dict payloads crossing architectural boundaries.
- Bare print for application logging.
- Mutable default arguments.
- Pydantic v1 APIs.
- Blocking I/O inside async code.
- New business logic inside entrypoints, web routes, or low-level infrastructure clients.

## Documentation Scope

- Keep this file focused on repository-wide architecture, layering, anti-patterns, migration rules, and quality gates.
- Keep path-specific rules in .github/instructions/*.instructions.md when specialization is needed.
- Keep operational defaults and command shortcuts in .github/copilot-settings.md.

## Definition of Done

A change is not complete unless all of these are true:

- Architecture boundaries are still respected.
- New code uses canonical imports.
- Tests were added or updated when behavior changed.
- Formatting, lint, type checking, and relevant tests were run or the reason they were not run is stated explicitly.
- No secrets or generated auth artifacts were introduced.

## Skill Routing

Load the relevant skill from .github/skills when the task matches:

- tinyflux-time-series for TinyFlux schema, queries, and aggregations.
- python-async-patterns for async use cases, adapters, and TaskGroup workflows.
- python-fastapi-patterns for FastAPI routes, dependencies, and request validation.
- jinja2-atomic-design for templates and HTMX fragments.
- python-typing-patterns for protocols, type vars, and advanced typing.
- uv-package-manager for dependency and environment changes.
- docker-best-practices for Dockerfile or entrypoint changes.
- hexagonal-architecture-video-publish for new VideoPublisher adapters.
- video-processing-migration for media pipeline migrations.
- python-observability-patterns for structured logging with structlog, logger setup, and log event formatting.
- python-resilience-patterns for retry logic, aiohttp session management, and timeout configuration.
- python-testing-respx for mocking outbound HTTP in tests with respx and create_autospec patterns.
