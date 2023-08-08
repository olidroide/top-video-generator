from datetime import timedelta, date

import structlog
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ConstrainedDate
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.status import HTTP_307_TEMPORARY_REDIRECT

from src.db_client import DatabaseClient, TimeseriesRange, YtAuth, TikTokAuth
from src.script_fetch_yt_data import main as script_fetch_yt_data
from src.script_generate_publish_top_video import main as script_weekly
from src.script_generate_vertical_publish_top_video import main as script_daily
from src.settings import get_app_settings
from src.tiktok_client import TikTokClient
from src.yt_client import get_yt_client

logger = structlog.get_logger()

app = FastAPI()


# app.add_middleware(
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"]
# )


@app.middleware("http")
async def validate_user(request: Request, call_next):
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
    method: str = None,
):
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
async def read_item(
    request: Request,
    code: str | None = None,
):
    if not code:
        logger.warning("Not CODE received in callback YT Auth", request=request.url)
        return RedirectResponse("/")

    oauth_credentials = get_yt_client().step_2_exchange_code_authentication(
        url_requested=str(request.url),
    )

    yt_auth = DatabaseClient().add_or_update_yt_auth(
        YtAuth(
            token=oauth_credentials.get("token"),
            refresh_token=oauth_credentials.get("refresh_token"),
            token_uri=oauth_credentials.get("token_uri"),
            client_id=oauth_credentials.get("client_id"),
            client_secret=oauth_credentials.get("client_secret"),
            scopes=oauth_credentials.get("scopes"),
        )
    )
    request.session["yt_credentials"] = yt_auth.client_id

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

    oauth_credentials = await TikTokClient().step_2_exchange_code_authentication(
        user_code=code,
    )

    tiktok_auth = DatabaseClient().add_or_update_tiktok_auth(
        TikTokAuth(
            token=oauth_credentials.get("access_token"),
            refresh_token=oauth_credentials.get("refresh_token"),
            client_id=oauth_credentials.get("open_id"),
            scopes=oauth_credentials.get("scope").split(","),
        )
    )
    request.session["tiktok_credentials"] = tiktok_auth.client_id

    return RedirectResponse("/")


class TimeseriesDailyDate(ConstrainedDate):
    la = date.today


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    daily: TimeseriesDailyDate = date.today(),
    weekly: TimeseriesDailyDate = None,
):
    try:
        video_list = DatabaseClient().get_top_25_videos(timeseries_range=TimeseriesRange.DAILY, day=daily)
    except Exception:
        video_list = []

    data_context = {
        "request": request,
        "video_list": video_list,
        "timeseries_range": TimeseriesRange.DAILY.value,
        "timeseries_weekly_date": weekly,
        "timeseries_daily_date": daily,
        "timeseries_next_date": daily + timedelta(days=1) if daily < date.today() else None,
        "timeseries_previous_date": daily - timedelta(days=1),
    }

    if yt_credentials := request.session.get("yt_credentials"):
        yt_client_id = yt_credentials
        yt_credentials_db = DatabaseClient().get_yt_auth(yt_client_id)
        data_context["yt_credentials"] = yt_credentials_db.dict()
    else:
        data_context["yt_authentication_url"] = get_yt_client().step_1_get_authentication_url()

    if tiktok_credential := request.session.get("tiktok_credentials"):
        tiktok_client_id = tiktok_credential
        tiktok_credentials_db = DatabaseClient().get_tiktok_auth(tiktok_client_id)
        data_context["tiktok_credentials"] = tiktok_credentials_db.dict()
    else:
        data_context["tiktok_authentication_url"] = await TikTokClient().step_1_get_authentication_url()

    return templates.TemplateResponse(
        "index.html",
        data_context,
    )


settings = get_app_settings()
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)