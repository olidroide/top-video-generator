"""Authentication, setup, and retry routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER, HTTP_307_TEMPORARY_REDIRECT, HTTP_403_FORBIDDEN

from src.application.authorize_use_case import (
    AuthorizeSpotifyRequest,
    AuthorizeTikTokCookiesRequest,
    AuthorizeYtRequest,
)
from src.application.get_setup_page_use_case import GetSetupPageRequest
from src.entrypoints.fetch_data import main_async as script_fetch_yt_data
from src.entrypoints.publish_vertical import main_async as script_daily
from src.entrypoints.publish_video import main_async as script_weekly
from src.web.dependencies import (
    AppSettingsDep,
    AuthorizeUseCaseDep,
    GetSetupPageUseCaseDep,
)
from src.web.state import logger, request_had_any_credentials, templates
from src.web.viewmodels import build_setup_page_view_model

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
    _use_case: AuthorizeUseCaseDep,
    _code: str | None = None,
    _scopes: str | None = None,
    _state: str | None = None,
    _error: str | None = None,
    _error_description: str | None = None,
) -> Response:
    logger.warning("tiktok.oauth_callback_deprecated", request=request.url)
    return RedirectResponse("/setup")


@router.post(
    "/tiktok_credentials/",
    response_class=RedirectResponse,
    status_code=HTTP_303_SEE_OTHER,
)
async def save_tiktok_credentials(
    request: Request,
    use_case: AuthorizeUseCaseDep,
    settings: AppSettingsDep,
    tiktok_cookies: Annotated[str, Form()],
) -> Response:
    cookies = tiktok_cookies.strip()
    if not cookies:
        logger.warning("tiktok.cookies_empty", request=request.url)
        return RedirectResponse("/setup", status_code=HTTP_303_SEE_OTHER)

    client_id = settings.tiktok_user_openid or "default"
    tiktok_auth_response = await use_case.execute_tiktok_cookies(
        AuthorizeTikTokCookiesRequest(cookies=cookies, client_id=client_id)
    )
    request.session["tiktok_credentials"] = tiktok_auth_response.client_id
    return RedirectResponse("/setup", status_code=HTTP_303_SEE_OTHER)


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

    try:
        spotify_auth_response = await use_case.execute_spotify(AuthorizeSpotifyRequest(code=code))
    except RuntimeError as exc:
        logger.exception("spotify_auth.callback_failed", error=str(exc))
        return RedirectResponse("/setup")

    request.session["spotify_credentials"] = spotify_auth_response.client_id

    return RedirectResponse("/")


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(
    request: Request,
    use_case: GetSetupPageUseCaseDep,
    settings: AppSettingsDep,
) -> Response:
    result = await use_case.execute(
        GetSetupPageRequest(
            yt_session_client_id=request.session.get("yt_credentials"),
            tiktok_session_client_id=request.session.get("tiktok_credentials"),
            spotify_session_client_id=request.session.get("spotify_credentials"),
            yt_auth_user_id=settings.yt_auth_user_id or None,
            tiktok_user_openid=settings.tiktok_user_openid or None,
            spotify_user_id=settings.spotify_user_id or None,
        )
    )

    if result.is_completed:
        return RedirectResponse("/")

    view_model = build_setup_page_view_model(result)

    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"request": request, "vm": view_model},
    )
