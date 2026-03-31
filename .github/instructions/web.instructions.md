---
applyTo: "src/web/**"
---

# Web Layer Rules

## Boundaries

- Routes delegate to `src.application` use cases only. No business logic, scoring, ranking, or direct DB queries in route handlers.
- Import infrastructure only through `src.web.dependencies` — never directly from `src.infrastructure` inside a router file.

## Canonical Imports

```python
from src.config.settings import get_app_settings   # never src.settings
from src.shared.logging import get_logger           # never print() or logging.getLogger
```

## Dependencies

Always use `Annotated[T, Depends(fn)]`. Define aliases in `src/web/dependencies.py`:

```python
from typing import Annotated
from fastapi import Depends

FetchTrendingDep = Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)]
```

## SSR Routes

```python
@router.get("/", response_class=HTMLResponse)
async def index(request: Request, use_case: FetchTrendingDep) -> Response:
    result = await use_case.execute(FetchTrendingRequest())
    return templates.TemplateResponse(request, "pages/index.html", {"videos": result.videos})
```

- Declare `Request` as first parameter on every HTML route.
- Always set `response_class=HTMLResponse` on routes that render templates.
- HTMX partial routes return fragment templates only — never a full page layout.
- Redirect with `status_code=303` after a successful POST.

## Lifespan

Use `lifespan` for startup/shutdown. Do not mix with `@app.on_event("startup")`.

## Testing

Override dependencies with `app.dependency_overrides` and `create_autospec`. Never reach infrastructure in web unit tests.
