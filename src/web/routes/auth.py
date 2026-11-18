"""Authentication and setup routes."""

import hmac
import secrets
from dataclasses import replace
from typing import Annotated
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER, HTTP_307_TEMPORARY_REDIRECT

from src.application.authorize_use_case import (
    AuthorizeTikTokCookiesRequest,
    AuthorizeYtRequest,
)
from src.application.get_setup_page_use_case import GetSetupPageRequest
from src.web.csrf import get_csrf_token, is_valid_csrf_token
from src.web.dependencies import (
    AppSettingsDep,
    AuthorizeUseCaseDep,
    GetSetupPageUseCaseDep,
)
from src.web.state import (
    YT_OAUTH_STATE_KEY,
    is_admin_authenticated,
    logger,
    templates,
)
from src.web.viewmodels import build_setup_page_view_model

router = APIRouter()


def _ensure_oauth_state_in_url(url: str | None, state: str) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if query.get("state"):
        return url
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    pairs.append(("state", state))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


@router.get(
    "/yt_auth/",
    response_class=RedirectResponse,
    status_code=HTTP_307_TEMPORARY_REDIRECT,
)
async def yt_auth(
    request: Request,
    use_case: AuthorizeUseCaseDep,
    code: str | None = None,
    state: str | None = None,
) -> Response:
    if not is_admin_authenticated(request):
        return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)

    expected_state = request.session.pop(YT_OAUTH_STATE_KEY, None)
    if not state or not expected_state or not hmac.compare_digest(state, expected_state):
        logger.warning("yt.oauth_state_mismatch", request=request.url)
        return RedirectResponse("/setup", status_code=HTTP_303_SEE_OTHER)

    if not code:
        logger.warning("Not CODE received in callback YT Auth", request=request.url)
        return RedirectResponse("/setup", status_code=HTTP_303_SEE_OTHER)

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
    if not is_admin_authenticated(request):
        return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)
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
    csrf_token: Annotated[str, Form()],
) -> Response:
    if not is_admin_authenticated(request):
        return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)

    if not is_valid_csrf_token(request, csrf_token):
        logger.warning("tiktok.cookies_csrf_failed", request=request.url)
        return HTMLResponse(status_code=403, content="Invalid CSRF token")

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


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(
    request: Request,
    use_case: GetSetupPageUseCaseDep,
    settings: AppSettingsDep,
) -> Response:
    if not is_admin_authenticated(request):
        return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)

    oauth_state = secrets.token_urlsafe(32)
    request.session[YT_OAUTH_STATE_KEY] = oauth_state
    result = await use_case.execute(
        GetSetupPageRequest(
            yt_session_client_id=request.session.get("yt_credentials"),
            tiktok_session_client_id=request.session.get("tiktok_credentials"),
            yt_auth_user_id=settings.yt_auth_user_id or None,
            tiktok_user_openid=settings.tiktok_user_openid or None,
            yt_oauth_state=oauth_state,
        )
    )

    if result.is_completed:
        return RedirectResponse("/")

    result = replace(
        result,
        yt_authentication_url=_ensure_oauth_state_in_url(result.yt_authentication_url, oauth_state),
    )
    view_model = build_setup_page_view_model(result)

    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={
            "request": request,
            "vm": view_model,
            "csrf_token": get_csrf_token(request),
        },
    )
