"""Authentication, setup, and retry routes."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_307_TEMPORARY_REDIRECT, HTTP_403_FORBIDDEN

from src.application.authorize_use_case import (
    AuthorizeSpotifyRequest,
    AuthorizeTikTokRequest,
    AuthorizeYtRequest,
)
from src.entrypoints.fetch_data import main_async as script_fetch_yt_data
from src.entrypoints.publish_vertical import main_async as script_daily
from src.entrypoints.publish_video import main_async as script_weekly
from src.web.dependencies import (
    AppSettingsDep,
    AuthenticationRepositoryDep,
    AuthorizeUseCaseDep,
    SpotifyProviderDep,
    TikTokProviderDep,
    YouTubeProviderDep,
)
from src.web.state import already_finish_setup, logger, request_had_any_credentials, templates

router = APIRouter()


@router.post("/retry/")
async def retry_operation(
    request: Request,
    background_tasks: BackgroundTasks,
    method: Literal["fetch", "daily", "weekly"] | None = None,
) -> JSONResponse:
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

    return JSONResponse(content={"message": f"Retried {method}" if task else f"Method {method} not found"})


@router.get(
    "/yt_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def yt_auth(
    request: Request,
    use_case: AuthorizeUseCaseDep,
    code: str | None = None,
) -> Response:
    if not code:
        logger.warning("Not CODE received in callback YT Auth", request=request.url)
        return RedirectResponse("/")

    yt_auth_response = await use_case.execute_yt(AuthorizeYtRequest(code=code, url_requested=str(request.url)))
    request.session["yt_credentials"] = yt_auth_response.client_id

    return RedirectResponse("/")


@router.get(
    "/tiktok_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def tiktok_auth(
    request: Request,
    use_case: AuthorizeUseCaseDep,
    code: str | None = None,
    _scopes: str | None = None,
    _state: str | None = None,
    _error: str | None = None,
    _error_description: str | None = None,
) -> Response:
    if not code:
        logger.warning("Not CODE received in callback TikTok Auth", request=request.url)
        return RedirectResponse("/")

    tiktok_auth_response = await use_case.execute_tiktok(AuthorizeTikTokRequest(code=code))
    request.session["tiktok_credentials"] = tiktok_auth_response.client_id

    return RedirectResponse("/")


@router.get(
    "/spotify_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def spotify_auth(
    request: Request,
    use_case: AuthorizeUseCaseDep,
    code: str | None = None,
    _scopes: str | None = None,
    _state: str | None = None,
    _error: str | None = None,
    _error_description: str | None = None,
) -> Response:
    if not code:
        logger.warning("Not CODE received in callback Spotify Auth", request=request.url)
        return RedirectResponse("/")

    spotify_auth_response = await use_case.execute_spotify(AuthorizeSpotifyRequest(code=code))
    request.session["spotify_credentials"] = spotify_auth_response.client_id

    return RedirectResponse("/")


@router.get("/setup")
async def setup_page(
    request: Request,
    auth_repo: AuthenticationRepositoryDep,
    yt_provider: YouTubeProviderDep,
    tiktok_provider: TikTokProviderDep,
    spotify_provider: SpotifyProviderDep,
    settings: AppSettingsDep,
) -> Response:
    if already_finish_setup(auth_repo, settings):
        return RedirectResponse("/")

    data_context: dict[str, object] = {
        "request": request,
    }

    if yt_credentials := request.session.get("yt_credentials"):
        yt_client_id = yt_credentials
        yt_credentials_db = auth_repo.get_yt_auth(yt_client_id)
        if yt_credentials_db:
            data_context["yt_credentials"] = yt_credentials_db.model_dump()
    else:
        data_context["yt_authentication_url"] = await yt_provider.step_1_get_authentication_url()

    if tiktok_credential := request.session.get("tiktok_credentials"):
        tiktok_client_id = tiktok_credential
        tiktok_credentials_db = auth_repo.get_tiktok_auth(tiktok_client_id)
        if tiktok_credentials_db:
            data_context["tiktok_credentials"] = tiktok_credentials_db.model_dump()
    else:
        data_context["tiktok_authentication_url"] = await tiktok_provider.step_1_get_authentication_url()

    if spotify_credential := request.session.get("spotify_credentials"):
        spotify_client_id = spotify_credential
        spotify_credentials_db = auth_repo.get_spotify_auth(spotify_client_id)
        if spotify_credentials_db:
            data_context["spotify_credentials"] = spotify_credentials_db.model_dump()
    else:
        data_context["spotify_authentication_url"] = await spotify_provider.step_1_get_authentication_url()

    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context=data_context,
    )
