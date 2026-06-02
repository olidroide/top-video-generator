"""Admin panel routes — Nothing-aesthetic connections dashboard."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from src.application.check_platform_connection_use_case import CheckPlatformConnectionRequest
from src.application.get_setup_page_use_case import GetSetupPageRequest
from src.application.trigger_admin_task_use_case import TriggerAdminTaskRequest
from src.domain.models import IntegrationCheckResult, IntegrationPlatform
from src.web.dependencies import (
    CheckPlatformConnectionUseCaseDep,
    GetAdminTaskStatusUseCaseDep,
    GetOperationalMetricsUseCaseDep,
    PublisherStateDep,
    PublisherStateWriterDep,
    ReleaseRepositoryDep,
    TimeSeriesRepositoryDep,
    TriggerAdminTaskUseCaseDep,
    VerifyPublishedVideosUseCaseDep,
    get_settings,
    get_setup_page_use_case,
)
from src.web.routes import ops as ops_routes
from src.web.state import get_app_version, logger, templates
from src.web.viewmodels import (
    AdminConnectionsViewModel,
    build_admin_connections_view_model,
    build_admin_data_connectors_view_model,
    build_admin_health_view_model,
    build_admin_metrics_view_model,
    build_admin_publishers_view_model,
    get_platform_connection_view_model,
)

if TYPE_CHECKING:
    from src.config.settings import AppSettings
else:
    AppSettings = Any

router = APIRouter(prefix="/admin")

_SESSION_KEY = "admin_authenticated"


def _is_admin(request: Request) -> bool:
    return bool(request.session.get(_SESSION_KEY))


def _password_matches(submitted: str, expected: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(submitted.encode(), expected.encode())


async def _extract_password(request: Request) -> str:
    body_text = (await request.body()).decode("utf-8")
    parsed = parse_qs(body_text, keep_blank_values=True)
    values = parsed.get("password")
    return values[0] if values else ""


async def _build_connections_context(
    request: Request,
    use_case: Annotated[Any, Depends(get_setup_page_use_case)],
    settings: Annotated[Any, Depends(get_settings)],
    check_results: dict[str, IntegrationCheckResult] | None = None,
) -> dict[str, object]:
    result = await use_case.execute(
        GetSetupPageRequest(
            yt_session_client_id=request.session.get("yt_credentials"),
            tiktok_session_client_id=request.session.get("tiktok_credentials"),
            yt_auth_user_id=settings.yt_auth_user_id or None,
            tiktok_user_openid=settings.tiktok_user_openid or None,
        )
    )
    return {
        "request": request,
        "vm": build_admin_connections_view_model(result, settings, check_results=check_results),
    }


def _parse_integration_platform(platform: str) -> IntegrationPlatform | None:
    try:
        return IntegrationPlatform(platform.lower())
    except ValueError:
        return None


@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(
    request: Request,
    settings: Annotated[Any, Depends(get_settings)],
) -> Response:
    if _is_admin(request):
        return RedirectResponse("/admin", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={
            "request": request,
            "error": None,
            "password_configured": bool(settings.admin_password),
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def admin_login_submit(
    request: Request,
    settings: Annotated[Any, Depends(get_settings)],
) -> Response:
    password = await _extract_password(request)
    expected = settings.admin_password or ""
    if expected and _password_matches(password, expected):
        request.session[_SESSION_KEY] = True
        logger.info(
            "admin.login_success",
            remote=request.client.host if request.client else "unknown",
        )
        return RedirectResponse("/admin", status_code=HTTP_303_SEE_OTHER)

    logger.warning(
        "admin.login_failed",
        remote=request.client.host if request.client else "unknown",
    )
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={
            "request": request,
            "error": "Invalid credentials.",
            "password_configured": bool(expected),
        },
        status_code=401,
    )


@router.get("/logout")
async def admin_logout(request: Request) -> Response:
    request.session.pop(_SESSION_KEY, None)
    logger.info(
        "admin.logout",
        remote=request.client.host if request.client else "unknown",
    )
    return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)


@router.get("", response_class=HTMLResponse)
async def admin_connections(
    request: Request,
    use_case: Annotated[Any, Depends(get_setup_page_use_case)],
    metrics_use_case: GetOperationalMetricsUseCaseDep,
    task_status_use_case: GetAdminTaskStatusUseCaseDep,
    publisher_state: PublisherStateDep,
    release_repo: ReleaseRepositoryDep,
    settings: Annotated[AppSettings, Depends(get_settings)],
    timeseries_repo: TimeSeriesRepositoryDep,
) -> Response:
    if not settings.admin_password:
        return HTMLResponse(status_code=503, content="Admin password not configured")
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=HTTP_303_SEE_OTHER)
    ctx = await _build_connections_context(request, use_case, settings)
    checks = {
        "ffmpeg": ops_routes.check_ffmpeg(),
        "templates": ops_routes.check_templates(settings),
        "database": ops_routes.check_database(timeseries_repo),
        "timeseries": ops_routes.check_timeseries_freshness(timeseries_repo),
    }
    overall_status = "healthy" if all(c["status"] == "ok" for c in checks.values()) else "unhealthy"
    health: dict[str, Any] = {"status": overall_status, "version": get_app_version(), "checks": checks}
    ctx["health_vm"] = build_admin_health_view_model(health)

    from src.web.viewmodels import build_admin_tasks_view_model

    tasks_vm = build_admin_tasks_view_model(task_status_use_case.execute())
    ctx["tasks"] = tasks_vm
    ctx["metrics_vm"] = build_admin_metrics_view_model(metrics_use_case.execute().to_dict())

    ctx["connectors"] = build_admin_data_connectors_view_model(settings=settings)
    ctx["publishers"] = build_admin_publishers_view_model(
        state_reader=publisher_state,
        release_store=release_repo,
        settings=settings,
    )

    return templates.TemplateResponse(request=request, name="admin/connections.html", context=ctx)


@router.get("/connections/status", response_class=HTMLResponse)
async def admin_connections_status(
    request: Request,
    use_case: Annotated[Any, Depends(get_setup_page_use_case)],
    settings: Annotated[Any, Depends(get_settings)],
) -> Response:
    """HTMX partial — returns the #connections-grid fragment only."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")
    ctx = await _build_connections_context(request, use_case, settings)
    return templates.TemplateResponse(
        request=request,
        name="admin/_connections_status.html",
        context=ctx,
    )


@router.post("/connections/{platform}/check", response_class=HTMLResponse)
async def admin_connection_check(
    request: Request,
    platform: str,
    setup_use_case: Annotated[Any, Depends(get_setup_page_use_case)],
    check_use_case: CheckPlatformConnectionUseCaseDep,
    settings: Annotated[Any, Depends(get_settings)],
) -> Response:
    """HTMX partial — returns a single platform card after a live check."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")

    integration_platform = _parse_integration_platform(platform)
    if integration_platform is None:
        return HTMLResponse(status_code=404, content="")

    check_result = await check_use_case.execute(CheckPlatformConnectionRequest(platform=integration_platform))
    ctx = await _build_connections_context(
        request,
        setup_use_case,
        settings,
        check_results={integration_platform.value: check_result},
    )

    view_model = cast("AdminConnectionsViewModel", ctx["vm"])
    platform_vm = get_platform_connection_view_model(view_model, platform)
    if platform_vm is None:
        return HTMLResponse(status_code=404, content="")

    return templates.TemplateResponse(
        request=request,
        name="admin/_platform_connection_card.html",
        context={"request": request, "p": platform_vm},
    )


@router.get("/health/status", response_class=HTMLResponse)
async def admin_health_status(
    request: Request,
    settings: Annotated[Any, Depends(get_settings)],
    timeseries_repo: TimeSeriesRepositoryDep,
) -> Response:
    """HTMX partial — returns the #health-checks fragment only."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")
    checks = {
        "ffmpeg": ops_routes.check_ffmpeg(),
        "templates": ops_routes.check_templates(settings),
        "database": ops_routes.check_database(timeseries_repo),
        "timeseries": ops_routes.check_timeseries_freshness(timeseries_repo),
    }
    overall_status = "healthy" if all(c["status"] == "ok" for c in checks.values()) else "unhealthy"
    health: dict[str, Any] = {"status": overall_status, "version": get_app_version(), "checks": checks}
    return templates.TemplateResponse(
        request=request,
        name="admin/_health_status.html",
        context={"request": request, "health_vm": build_admin_health_view_model(health)},
    )


@router.get("/tasks/status", response_class=HTMLResponse)
async def admin_tasks_status(
    request: Request,
    task_status_use_case: GetAdminTaskStatusUseCaseDep,
) -> Response:
    """HTMX partial — returns the #tasks-grid fragment with task status cards."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")

    # Build view model from repos
    from src.web.viewmodels import build_admin_tasks_view_model

    tasks_vm = build_admin_tasks_view_model(task_status_use_case.execute())

    return templates.TemplateResponse(
        request=request,
        name="admin/_tasks_status.html",
        context={"request": request, "tasks": tasks_vm},
    )


@router.get("/metrics/status", response_class=HTMLResponse)
async def admin_metrics_status(
    request: Request,
    metrics_use_case: GetOperationalMetricsUseCaseDep,
) -> Response:
    """HTMX partial — returns the #metrics-grid fragment with persisted counters."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")

    return templates.TemplateResponse(
        request=request,
        name="admin/_metrics_status.html",
        context={
            "request": request,
            "metrics_vm": build_admin_metrics_view_model(metrics_use_case.execute().to_dict()),
        },
    )


def _normalize_task_publisher(method: str, publisher: str | None) -> str | None:
    normalized_publisher = publisher.lower() if publisher else None
    if normalized_publisher and normalized_publisher not in _VALID_PUBLISHER_SLUGS:
        msg = f"Invalid publisher '{publisher}'."
        raise ValueError(msg)
    if method != "daily" and normalized_publisher:
        raise ValueError("'publisher' is only supported for daily task.")
    return normalized_publisher


def _resolve_task_runner(
    *,
    method: str,
    force: bool,
    normalized_publisher: str | None,
) -> tuple[str, Any]:
    if method == "fetch":
        from src.entrypoints.fetch_data import main_async as fetch_main_async

        async def _run_fetch_task() -> None:
            await fetch_main_async(force_fetch=force)

        return ("fetch", _run_fetch_task)
    if method == "daily":
        from src.entrypoints.publish_vertical import main_async as publish_vertical_main_async

        async def _run_daily_task() -> None:
            await publish_vertical_main_async(
                target_publishers=(normalized_publisher,) if normalized_publisher else None,
            )

        return ("daily", _run_daily_task)
    if method == "weekly":
        from src.entrypoints.publish_video import main_async as publish_weekly_main_async

        return ("weekly", publish_weekly_main_async)
    msg = f"Unsupported task method '{method}'"
    raise ValueError(msg)


@router.post("/tasks/{method}/trigger", response_class=HTMLResponse)
async def trigger_admin_task(
    request: Request,
    method: str,
    background_tasks: BackgroundTasks,
    trigger_use_case: TriggerAdminTaskUseCaseDep,
    force: bool = False,
    publisher: str | None = None,
) -> Response:
    """HTMX endpoint — validates and triggers a background task (fetch/daily/weekly)."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")

    # Validate and authorize
    trigger_result = trigger_use_case.execute(
        TriggerAdminTaskRequest(
            task_method=method,
            user_ip=request.client.host if request.client else "unknown",
        )
    )

    if not trigger_result.queued:
        # Validation failed
        from starlette.responses import PlainTextResponse

        return PlainTextResponse(content=f"Error: {trigger_result.message}", status_code=400)

    # Dispatch background task
    async def _run_with_task_tracking(task_method: str, task_fn: Any) -> None:
        try:
            await task_fn()
            trigger_use_case.mark_completed(task_method=task_method)
        except Exception as exc:
            trigger_use_case.mark_failed(task_method=task_method, error_message=str(exc))
            raise

    try:
        normalized_publisher = _normalize_task_publisher(method, publisher)
        run_task_method, task_fn = _resolve_task_runner(
            method=method,
            force=force,
            normalized_publisher=normalized_publisher,
        )
    except ValueError as exc:
        from starlette.responses import PlainTextResponse

        return PlainTextResponse(content=f"Error: {exc}", status_code=400)

    background_tasks.add_task(_run_with_task_tracking, run_task_method, task_fn)

    # Return feedback to HTMX
    return templates.TemplateResponse(
        request=request,
        name="admin/_task_feedback.html",
        context={
            "request": request,
            "message": trigger_result.message,
            "task_method": method,
        },
    )


@router.get("/verify", response_class=HTMLResponse)
async def admin_verify_published(
    request: Request,
    verify_use_case: VerifyPublishedVideosUseCaseDep,
) -> Response:
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")

    report = await verify_use_case.execute()
    return templates.TemplateResponse(
        request=request,
        name="admin/_verification_results.html",
        context={"request": request, "report": report},
    )


@router.get("/tasks/logs/{method}", response_class=HTMLResponse)
async def admin_task_logs(
    request: Request,
    method: str,
    task_status_use_case: GetAdminTaskStatusUseCaseDep,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> Response:
    """HTMX partial — returns live log lines for a running task."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")

    valid_methods = {"fetch", "daily", "weekly"}
    if method not in valid_methods:
        return HTMLResponse(status_code=404, content="")

    log_path = Path(settings.log_file_path)
    if not log_path.is_file():  # noqa: ASYNC240
        return templates.TemplateResponse(
            request=request,
            name="admin/_task_logs.html",
            context={"request": request, "method": method, "lines": [], "task_complete": True},
        )

    task_started_at = task_status_use_case.get_task_started_at(method)
    latest_status = task_status_use_case.execute().latest_status_by_method.get(method)
    task_complete = latest_status not in ("queued", None)

    lines = _read_log_lines(log_path, task_started_at)

    return templates.TemplateResponse(
        request=request,
        name="admin/_task_logs.html",
        context={
            "request": request,
            "method": method,
            "lines": lines,
            "task_complete": task_complete,
        },
    )


def _read_log_lines(log_path: Path, since_timestamp: float | None) -> list[dict[str, str]]:
    """Delegate to shared log utils."""
    from src.shared.log_utils import read_log_lines_since

    return read_log_lines_since(log_path, since_timestamp, max_lines=80)


@router.get("/connectors/status", response_class=HTMLResponse)
async def admin_connectors_status(
    request: Request,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> Response:
    """HTMX partial — returns the #connectors-grid fragment."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")
    connectors = build_admin_data_connectors_view_model(settings=settings)
    return templates.TemplateResponse(
        request=request,
        name="admin/_data_connectors_status.html",
        context={"request": request, "connectors": connectors},
    )


@router.get("/publishers/status", response_class=HTMLResponse)
async def admin_publishers_status(
    request: Request,
    publisher_state: PublisherStateDep,
    release_repo: ReleaseRepositoryDep,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> Response:
    """HTMX partial — returns the #publishers-grid fragment."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")
    publishers = build_admin_publishers_view_model(
        state_reader=publisher_state,
        release_store=release_repo,
        settings=settings,
    )
    return templates.TemplateResponse(
        request=request,
        name="admin/_publishers_status.html",
        context={"request": request, "publishers": publishers},
    )


_VALID_PUBLISHER_SLUGS = {"youtube", "tiktok", "instagram"}


@router.post("/publishers/{slug}/toggle", response_class=HTMLResponse)
async def toggle_publisher(
    request: Request,
    slug: str,
    publisher_state: PublisherStateDep,
    publisher_state_writer: PublisherStateWriterDep,
    release_repo: ReleaseRepositoryDep,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> Response:
    """HTMX endpoint — toggle publisher enabled state."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")
    if slug not in _VALID_PUBLISHER_SLUGS:
        return HTMLResponse(status_code=404, content="")

    current_enabled = publisher_state.is_enabled(slug)
    next_enabled = not current_enabled
    publisher_state_writer.set_enabled(slug, next_enabled)
    logger.info(
        "admin.publisher_toggled",
        slug=slug,
        enabled=next_enabled,
        remote=request.client.host if request.client else "unknown",
    )

    publishers = build_admin_publishers_view_model(
        state_reader=publisher_state,
        release_store=release_repo,
        settings=settings,
    )
    publisher = next((pub for pub in publishers.publishers if pub.slug == slug), None)
    if publisher is None:
        return HTMLResponse(status_code=404, content="")

    return templates.TemplateResponse(
        request=request,
        name="admin/_publisher_card.html",
        context={"request": request, "pub": publisher},
    )


@router.post("/publishers/{slug}/check-auth", response_class=HTMLResponse)
async def check_publisher_auth(
    request: Request,
    slug: str,
    publisher_state: PublisherStateDep,
    release_repo: ReleaseRepositoryDep,
    check_use_case: CheckPlatformConnectionUseCaseDep,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> Response:
    """HTMX endpoint — check auth status for a publisher and return single card."""
    if not _is_admin(request):
        return HTMLResponse(status_code=403, content="")
    if slug not in _VALID_PUBLISHER_SLUGS:
        return HTMLResponse(status_code=404, content="")

    integration_platform = _parse_integration_platform(slug)
    if integration_platform is None:
        return HTMLResponse(status_code=404, content="")

    check_result = await check_use_case.execute(CheckPlatformConnectionRequest(platform=integration_platform))

    publishers = build_admin_publishers_view_model(
        state_reader=publisher_state,
        release_store=release_repo,
        settings=settings,
        check_results={slug: check_result},
    )
    publisher = next((pub for pub in publishers.publishers if pub.slug == slug), None)
    if publisher is None:
        return HTMLResponse(status_code=404, content="")

    return templates.TemplateResponse(
        request=request,
        name="admin/_publisher_card.html",
        context={"request": request, "pub": publisher},
    )
