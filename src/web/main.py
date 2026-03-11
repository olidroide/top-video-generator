import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import flag
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_307_TEMPORARY_REDIRECT, HTTP_403_FORBIDDEN

from src.config.settings import get_app_settings
from src.db_client import DatabaseClient, ReleasePlatform, SpotifyAuth, TikTokAuth, TimeseriesRange, YtAuth
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.social.tiktok_client import TikTokClient
from src.infrastructure.youtube import get_yt_client
from src.script_fetch_yt_data import main as script_fetch_yt_data
from src.script_generate_publish_top_video import main as script_weekly
from src.script_generate_vertical_publish_top_video import main as script_daily
from src.shared.logging import get_logger

logger = get_logger(__name__)

app = FastAPI()


# app.add_middleware(
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"]
# )


async def request_had_any_credentials(request: Request) -> bool:
    return bool(
        request.session.get("yt_credentials")
        or request.session.get("tiktok_credentials")
        or request.session.get("spotify_credentials")
    )


async def already_finish_setup() -> bool:
    db_client = DatabaseClient()
    if not db_client.get_yt_auth(settings.yt_auth_user_id or ""):
        return False

    if not db_client.get_tiktok_auth(settings.tiktok_user_openid or ""):
        return False

    if not db_client.get_spotify_auth(settings.spotify_user_id or ""):
        return False

    return True


@app.middleware("http")
async def validate_user(request: Request, call_next: RequestResponseEndpoint) -> Response:
    # print(request.session)
    response = await call_next(request)
    return response


app.mount("/static", StaticFiles(directory="web/static"), name="static")

templates = Jinja2Templates(directory="web/templates")


@app.post(
    "/retry/",
)
async def read_item(
    request: Request,
    background_tasks: BackgroundTasks,
    method: str | None = None,
):
    if not await request_had_any_credentials(request):
        return JSONResponse(
            content={"message": f"Method {method} forbidden"},
            status_code=HTTP_403_FORBIDDEN,
        )

    task = None
    if method == "fetch":
        task = script_fetch_yt_data
    elif method == "daily":
        task = script_daily
    elif method == "weekly":
        task = script_weekly

    if task:
        background_tasks.add_task(task)

    return {"message": f"Retried {method}" if task else f"Method {method} not found"}


@app.get(
    "/yt_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def yt_auth(
    request: Request,
    code: str | None = None,
):
    if not code:
        logger.warning("Not CODE received in callback YT Auth", request=request.url)
        return RedirectResponse("/")

    yt_client: Any = get_yt_client()
    oauth_credentials: dict[str, Any] = cast(
        dict[str, Any],
        yt_client.step_2_exchange_code_authentication(
            url_requested=str(request.url),
        ),
    )

    yt_auth_response = DatabaseClient().add_or_update_yt_auth(
        YtAuth(
            token=oauth_credentials.get("token"),
            refresh_token=oauth_credentials.get("refresh_token"),
            token_uri=oauth_credentials.get("token_uri"),
            client_id=oauth_credentials.get("client_id"),
            client_secret=oauth_credentials.get("client_secret"),
            scopes=oauth_credentials.get("scopes"),
        )
    )
    request.session["yt_credentials"] = yt_auth_response.client_id

    return RedirectResponse("/")


@app.get(
    "/tiktok_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def tiktok_auth(
    request: Request,
    code: str | None = None,
    scopes: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    if not code:
        logger.warning("Not CODE received in callback TikTok Auth", request=request.url)
        return RedirectResponse("/")

    oauth_credentials: dict[str, Any] = cast(
        dict[str, Any],
        await TikTokClient().step_2_exchange_code_authentication(
            user_code=code,
        ),
    )

    tiktok_auth_response = DatabaseClient().add_or_update_tiktok_auth(
        TikTokAuth(
            token=oauth_credentials.get("access_token"),
            refresh_token=oauth_credentials.get("refresh_token"),
            client_id=oauth_credentials.get("open_id"),
            scopes=str(oauth_credentials.get("scope") or "").split(","),
        )
    )
    request.session["tiktok_credentials"] = tiktok_auth_response.client_id

    return RedirectResponse("/")


@app.get(
    "/spotify_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def spotify_auth(
    request: Request,
    code: str | None = None,
    scopes: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    if not code:
        logger.warning("Not CODE received in callback Spotify Auth", request=request.url)
        return RedirectResponse("/")

    spotify_client: Any = SpotifyClient()
    oauth_credentials: dict[str, Any] = cast(
        dict[str, Any],
        await spotify_client.step_2_exchange_code_authentication(
            user_code=code,
        ),
    )

    spotify_auth_response = DatabaseClient().add_or_update_spotify_auth(
        SpotifyAuth(
            token=oauth_credentials.get("access_token"),
            refresh_token=oauth_credentials.get("refresh_token"),
            client_id=oauth_credentials.get("client_id"),
            scopes=str(oauth_credentials.get("scope") or "").split(" "),
        )
    )
    request.session["spotify_credentials"] = spotify_auth_response.client_id

    return RedirectResponse("/")


class TimeseriesDailyDateModel(BaseModel):
    value: date

    @field_validator("value")
    @classmethod
    def validate_date(cls, v: date) -> date:
        return v


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    daily: TimeseriesDailyDateModel | None = None,
    weekly: TimeseriesDailyDateModel | None = None,
):
    timeseries_range = TimeseriesRange.WEEKLY if weekly else TimeseriesRange.DAILY
    daily_date = date.today() if not daily else daily.value
    weekly_date = weekly.value if weekly else None
    try:
        db_client = DatabaseClient()
        video_list = db_client.get_top_25_videos(
            timeseries_range=timeseries_range, day=weekly_date if weekly_date else daily_date
        )
        yt_video_published = db_client.is_release_at_date(release_platform=ReleasePlatform.YT, release_date=daily_date)
    except Exception:
        video_list = []
        yt_video_published = False

    credentials_owner = await request_had_any_credentials(request)
    title_flag = flag.flag(get_app_settings().yt_search_region_code or "")
    data_context: dict[str, Any] = {
        "request": request,
        "video_list": video_list,
        "timeseries_range": timeseries_range.value,
        "timeseries_weekly_date": weekly_date,
        "timeseries_daily_date": daily_date,
        "timeseries_next_date": daily_date + timedelta(days=1) if daily_date < date.today() else None,
        "timeseries_previous_date": daily_date - timedelta(days=1),
        "yt_video_published": yt_video_published,
        "credentials_owner": credentials_owner,
        "title_page": f"{title_flag} 🔝 VIDEO GENERATOR",
    }

    return templates.TemplateResponse(
        "index.html",
        data_context,
    )


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(
    request: Request,
):
    if await already_finish_setup():
        return RedirectResponse("/")

    data_context: dict[str, Any] = {
        "request": request,
    }

    if yt_credentials := request.session.get("yt_credentials"):
        yt_client_id = yt_credentials
        yt_credentials_db = DatabaseClient().get_yt_auth(yt_client_id)
        if yt_credentials_db:
            data_context["yt_credentials"] = yt_credentials_db.model_dump()
    else:
        data_context["yt_authentication_url"] = await get_yt_client().step_1_get_authentication_url()

    if tiktok_credential := request.session.get("tiktok_credentials"):
        tiktok_client_id = tiktok_credential
        tiktok_credentials_db = DatabaseClient().get_tiktok_auth(tiktok_client_id)
        if tiktok_credentials_db:
            data_context["tiktok_credentials"] = tiktok_credentials_db.model_dump()
    else:
        data_context["tiktok_authentication_url"] = await TikTokClient().step_1_get_authentication_url()

    if spotify_credential := request.session.get("spotify_credentials"):
        spotify_client_id = spotify_credential
        spotify_credentials_db = DatabaseClient().get_spotify_auth(spotify_client_id)
        if spotify_credentials_db:
            data_context["spotify_credentials"] = spotify_credentials_db.model_dump()
    else:
        data_context["spotify_authentication_url"] = await SpotifyClient().step_1_get_authentication_url()

    return templates.TemplateResponse(
        "setup.html",
        data_context,
    )


settings = get_app_settings()
app.add_middleware(cast(Any, SessionMiddleware), secret_key=settings.app_secret_key or "dev-secret")


# Health check and metrics storage
_health_status: dict[str, Any] = {"status": "healthy", "checks": {}}
_metrics = {
    "fetch_count": 0,
    "fetch_errors": 0,
    "upload_count": 0,
    "upload_errors": 0,
    "processing_count": 0,
    "processing_errors": 0,
}


class HealthCheck(BaseModel):
    status: str
    version: str = "1.0.0"
    checks: dict[str, dict[str, str]]


class MetricsResponse(BaseModel):
    fetch_count: int
    fetch_errors: int
    upload_count: int
    upload_errors: int
    processing_count: int
    processing_errors: int


def _check_ffmpeg() -> dict[str, str]:
    """Check if ffmpeg is available."""
    try:
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return {"status": "error", "message": "ffmpeg not found"}

        result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)  # noqa: S603
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "message": "ffmpeg available" if result.returncode == 0 else "ffmpeg error",
        }
    except Exception as e:
        return {"status": "error", "message": f"ffmpeg not found: {e}"}


def _check_templates() -> dict[str, str]:
    """Check if required template files exist."""
    settings = get_app_settings()
    required_files = [
        settings.video_template_file,
        settings.video_template_vertical_file,
        settings.video_template_thumbnail_file,
        settings.video_template_thumbnail_font_file,
    ]

    required_paths = [f for f in required_files if f]
    missing = [f for f in required_paths if not Path(f).exists()]

    return {
        "status": "ok" if not missing else "error",
        "message": "All templates present" if not missing else f"Missing templates: {missing}",
    }


def _check_database() -> dict[str, str]:
    """Check database connectivity."""
    try:
        db = DatabaseClient()
        # Try to get some data to verify connection
        _ = db.get_top_25_videos(TimeseriesRange.DAILY, date.today())
        return {"status": "ok", "message": "Database accessible"}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {e}"}


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint for monitoring."""
    checks = {
        "ffmpeg": _check_ffmpeg(),
        "templates": _check_templates(),
        "database": _check_database(),
    }

    # Overall status is error if any check fails
    overall_status = "healthy" if all(c["status"] == "ok" for c in checks.values()) else "unhealthy"

    return HealthCheck(status=overall_status, checks=checks)


@app.get("/metrics")
async def metrics():
    """Metrics endpoint for monitoring."""
    return MetricsResponse(**_metrics)


@app.post("/metrics/increment/{metric_name}")
async def increment_metric(metric_name: str, error: bool = False):
    """Internal endpoint to increment metrics (used by background tasks)."""
    if metric_name in _metrics:
        if error:
            _metrics[f"{metric_name}_errors"] += 1
        else:
            _metrics[metric_name] += 1
    return {"status": "ok"}
