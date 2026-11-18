"""
FastAPI delivery layer template — project-aligned.

Routes are thin: parse → auth → delegate to use case → render.
No business logic, scoring, ranking, or repository access in routes.

Run:
    uv run uvicorn src.web.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config.settings import get_app_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Lifespan — wire application-level dependencies here, not in routes.
# Do NOT mix with @app.on_event("startup") / @app.on_event("shutdown").
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_app_settings()
    logger.info("startup", env=getattr(settings, "env", "production"))
    yield
    logger.info("shutdown")


# =============================================================================
# Application
# =============================================================================

app = FastAPI(title="top-video-generator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
templates = Jinja2Templates(directory="src/web/templates")


# =============================================================================
# Use-case dependencies
# Wire real use cases from src.application.* below.
# =============================================================================

# Example wiring:
#
# from src.application.fetch_trending_use_case import FetchTrendingUseCase
# from src.domain.models import FetchTrendingRequest
# from src.infrastructure.storage.video_repository import VideoRepository
#
# def get_video_repository() -> VideoRepository:
#     settings = get_app_settings()
#     return VideoRepository(db_path=settings.db_path)
#
# def get_fetch_trending_use_case(
#     repo: Annotated[VideoRepository, Depends(get_video_repository)],
# ) -> FetchTrendingUseCase:
#     return FetchTrendingUseCase(repository=repo)
#
# FetchTrendingDep = Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)]


# =============================================================================
# Router — thin SSR routes
# =============================================================================

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Response:
    """
    Full-page SSR route.
    Replace stub with:
        use_case: Annotated[FetchTrendingUseCase, Depends(get_fetch_trending_use_case)]
    and call:
        result = await use_case.execute(FetchTrendingRequest())
    """
    return templates.TemplateResponse(request, "pages/index.html", {"videos": []})


@router.get("/partials/video-list", response_class=HTMLResponse)
async def video_list_partial(request: Request) -> Response:
    """HTMX swap target — returns fragment only, not a full page."""
    return templates.TemplateResponse(request, "partials/video_list.html", {"videos": []})


@router.post("/publish", response_class=HTMLResponse)
async def publish_action(
    request: Request,
    video_id: Annotated[str, Form()],
) -> Response:
    """
    Form action — delegate to use case, redirect on success, re-render on failure.
    Replace stub with:
        result = await use_case.execute(PublishVideoRequest(video_id=video_id))
        if not result.success:
            return templates.TemplateResponse(
                request, "pages/publish.html", {"error": result.error}, status_code=422
            )
    """
    logger.info("publish_requested", video_id=video_id)
    return RedirectResponse(url="/", status_code=303)


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.web.main:app", host="0.0.0.0", port=8000, reload=True)
