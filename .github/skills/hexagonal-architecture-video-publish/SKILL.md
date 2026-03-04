---
name: hexagonal-architecture-video-publish
description: "Hexagonal Architecture (Ports and Adapters) for video fetch and multi-platform publishing in this repository. Triggers on: hexagonal, ports, adapters, protocol, publisher registry, canonical models, vertical publish."
compatibility: "Python 3.11+, Pydantic v2, asyncio.TaskGroup."
---

# Hexagonal Architecture for Video Publish

Use this skill when creating or refactoring fetch/publish flows for YouTube/TikTok/Instagram.

## Goal

Keep core orchestration independent from external platforms by enforcing:

- domain models as the canonical internal schema
- protocols as ports
- platform clients as adapters
- registry-based dependency wiring

## Required Structure

```text
src/
├── domain/
│   ├── models.py
│   └── ports.py
├── adapters/
│   ├── youtube_source.py
│   ├── youtube_publisher.py
│   ├── tiktok_publisher.py
│   └── instagram_publisher.py
└── infrastructure/
    └── publisher_registry.py
```

## Layer Contracts

- `src/domain/models.py`
- Define canonical models used internally: `CanonicalVideo`, `PublishingResult`, `Platform`, `VideoScoreStatus`.
- Include helper/computed fields needed by multiple adapters (for example `yt_url`, `title_cleaned`).

- `src/domain/ports.py`
- Define protocol ports with `typing.Protocol` and `@runtime_checkable`.
- `VideoDataSource` handles fetching and normalization into canonical models.
- `VideoPublisher` handles platform publishing and returns `PublishingResult`.

- `src/adapters/*.py`
- Each adapter must implement one port and translate external client data into canonical models.
- Keep platform-specific auth and API usage inside adapters.
- Wrap failures and return a failed `PublishingResult` instead of propagating fatal platform exceptions.

- `src/infrastructure/publisher_registry.py`
- Build enabled publishers from settings.
- Defer imports inside the builder function to avoid import-time hard failures from optional dependencies.

## Script Refactor Pattern

For `src/script_generate_vertical_publish_top_video.py`:

- Fetch or load videos as canonical models.
- Render media pipeline as today (downloader/workers/video processing).
- Build publishers via `build_publishers()`.
- Publish concurrently with `asyncio.TaskGroup`.
- Persist each platform result independently.

## Non-Negotiable Rules

- Domain must not depend on concrete external clients.
- Orchestrator must not import concrete publisher classes.
- New platform support requires only:
  1. new adapter implementing `VideoPublisher`
  2. registry registration
- A failure in one platform must not stop publishing on others.

## Quality Gates

- Type checks pass for protocol signatures.
- Lint/format pass (`ruff`, `ruff format`).
- Vertical publish script supports test doubles by port interface.
- Logs use `src/logger.py` and include platform identifiers for publish outcomes.

## Copilot Task Prompt Template

```text
Create/update domain ports and adapters using Hexagonal Architecture for publishing.
Requirements:
1) Canonical models in src/domain/models.py
2) Protocol ports in src/domain/ports.py
3) Adapters in src/adapters/ for YouTube/TikTok/Instagram
4) build_publishers() registry in src/infrastructure/publisher_registry.py
5) Refactor src/script_generate_vertical_publish_top_video.py to publish in parallel using asyncio.TaskGroup and persist per-platform results.
Constraints:
- Orchestrator cannot import concrete publisher adapters directly.
- Domain cannot import external clients.
- Return failed PublishingResult on platform exceptions.
```
