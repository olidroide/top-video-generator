---
name: python-fastapi-patterns
description: "FastAPI delivery layer patterns for thin routes, SSR with Jinja2/HTMX, and hexagonal architecture wiring. Triggers on: fastapi, api endpoint, dependency injection, pydantic model, TemplateResponse, HTMX, Jinja2, starlette, route handler, uvicorn."
compatibility: "FastAPI 0.100+, Pydantic v2, Python 3.12+. Requires uvicorn for production."
---

# FastAPI Delivery Layer Patterns

## Core Mandate

**Routes must not contain business logic.** A route handler has exactly four responsibilities:

1. Parse and validate the inbound request (path/query params, body, form fields)
2. Authenticate / authorize the caller (via `Depends`)
3. Delegate to an application use case from `src.application`
4. Render the response (`TemplateResponse` for SSR pages/partials, `JSONResponse` only where appropriate)

```python
# ✅ Correct: thin route delegates to use case, renders template
@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    use_case: Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)],
) -> Response:
    result = await use_case.execute(FetchTrendingRequest())
    return templates.TemplateResponse(
        request, "pages/index.html", {"videos": result.videos}
    )

# ❌ Wrong: business logic and direct infrastructure access in route
@router.get("/")
async def index(db: DB):
    videos = await db.query(Video).order_by(Video.score.desc()).limit(10).all()
    return {"videos": videos}
```

## Canonical Imports

```python
from src.config.settings import get_app_settings   # never src.settings
from src.shared.logging import get_logger           # never src.logger or print
from src.application.fetch_trending_use_case import FetchTrendingUseCase
from src.domain.models import CanonicalVideo
```

Never import from `src.db_client`, `src.settings`, or `src.logger` in web routes.

## Lifespan — Application Wiring

Use `lifespan` to wire dependencies once at startup. **Do not mix with `@app.on_event("startup")`** — FastAPI requires one or the other, not both.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.config.settings import get_app_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_app_settings()
    logger.info("startup", env=settings.env)
    yield
    logger.info("shutdown")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
templates = Jinja2Templates(directory="src/web/templates")
```

## SSR Routes with Jinja2

Routes that render HTML must:

- Declare `Request` as first parameter
- Declare `response_class=HTMLResponse`
- Return `templates.TemplateResponse(request, template_path, context)`

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from typing import Annotated

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    use_case: Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)],
) -> Response:
    result = await use_case.execute(FetchTrendingRequest())
    return templates.TemplateResponse(
        request, "pages/index.html", {"videos": result.videos}
    )
```

## HTMX Partial Responses

HTMX partials are regular routes that return a fragment template. Never return a full page from an HTMX swap target.

```python
@router.get("/partials/video-list", response_class=HTMLResponse)
async def video_list_partial(
    request: Request,
    use_case: Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)],
) -> Response:
    result = await use_case.execute(FetchTrendingRequest())
    return templates.TemplateResponse(
        request, "partials/video_list.html", {"videos": result.videos}
    )
```

## Form Handling

Validate at the boundary with `Form(...)`. Delegate to use case. Redirect (303) on success, re-render with error (422) on failure.

```python
from fastapi import Form
from fastapi.responses import RedirectResponse

@router.post("/publish", response_class=HTMLResponse)
async def publish_video(
    request: Request,
    video_id: Annotated[str, Form()],
    use_case: Annotated[PublishVideoUseCase, Depends(get_publish_video_use_case)],
) -> Response:
    result = await use_case.execute(PublishVideoRequest(video_id=video_id))
    if not result.success:
        return templates.TemplateResponse(
            request,
            "pages/publish.html",
            {"error": result.error},
            status_code=422,
        )
    return RedirectResponse(url="/", status_code=303)
```

## Dependency Wiring — Use Cases

Wire use cases through `Depends`. Routes must not read repositories or infrastructure clients directly.

```python
from fastapi import Depends
from typing import Annotated
from src.application.fetch_trending_use_case import FetchTrendingUseCase
from src.infrastructure.storage.video_repository import VideoRepository
from src.config.settings import get_app_settings

def get_video_repository() -> VideoRepository:
    settings = get_app_settings()
    return VideoRepository(db_path=settings.db_path)

def get_fetch_trending_use_case(
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
) -> FetchTrendingUseCase:
    return FetchTrendingUseCase(repository=repo)

# Annotated alias for reuse across routes
FetchTrendingDep = Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)]
```

## Router Organization

```python
# src/web/routers/dashboard.py
from fastapi import APIRouter
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# src/web/main.py
from src.web.routers import dashboard, publish
app.include_router(dashboard.router)
app.include_router(publish.router)
```

## Testing Web Routes

Use `TestClient` with `dependency_overrides` to swap use cases without touching infrastructure.

```python
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, create_autospec
from src.web.main import app
from src.web.dependencies import get_fetch_trending_use_case

def test_index_renders_video_list():
    mock_use_case = create_autospec(FetchTrendingUseCase, instance=True)
    mock_use_case.execute = AsyncMock(return_value=FetchTrendingResult(videos=[...]))
    app.dependency_overrides[get_fetch_trending_use_case] = lambda: mock_use_case

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert b"video-list" in response.content

    app.dependency_overrides.clear()
```

## Anti-Patterns

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| Business logic inside route | Delegate to `src.application` use case |
| `app.state.db` accessed in route | Wire repo/use case via `Depends` |
| `from src.settings import settings` | `from src.config.settings import get_app_settings` |
| `print(...)` in route | `logger = get_logger(__name__)` |
| `@app.on_event("startup")` + `lifespan` | Use `lifespan` exclusively |
| Full page returned from HTMX swap target | Return fragment template only |
| Route directly queries DB or calls clients | Route calls use case; use case owns infra |

## Additional Resources

- `./references/dependency-injection.md` — Advanced DI patterns, dependency overrides for testing
- `./references/middleware-patterns.md` — Security headers, CORS, request ID tracking
- `./references/validation-serialization.md` — Pydantic v2 validators, computed fields
- `./references/background-tasks.md` — `BackgroundTasks` for post-response side effects
- `./scripts/scaffold-api.sh` — Generate thin-route + use-case boilerplate
- `./assets/fastapi-template.py` — Project-aligned FastAPI app skeleton

## See Also

- `jinja2-atomic-design` — Template structure, HTMX components, atomic design
- `python-async-patterns` — Async use cases, TaskGroup workflows
- `hexagonal-architecture-video-publish` — Publisher wiring and adapter patterns
