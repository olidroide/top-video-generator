#!/usr/bin/env bash
# Generate a thin FastAPI route file with SSR + use-case wiring boilerplate.
#
# Routes must only: parse request → call use case → render response.
# No business logic, scoring, ranking, or repository access in route files.
#
# Usage: scaffold-api.sh <feature_name>
# Example: scaffold-api.sh dashboard

set -euo pipefail

FEATURE="${1:-}"

if [[ -z "$FEATURE" ]]; then
    echo "Usage: scaffold-api.sh <feature_name>"
    echo "Example: scaffold-api.sh dashboard"
    exit 1
fi

FEATURE_LOWER=$(echo "$FEATURE" | tr '[:upper:]' '[:lower:]')
FEATURE_TITLE=$(echo "$FEATURE_LOWER" | sed 's/\b\(.\)/\u\1/g')

cat << EOF
# src/web/routers/${FEATURE_LOWER}.py
"""
${FEATURE_TITLE} delivery routes — thin router.

Routes must only: parse request → call use case → render response.
No business logic, scoring, ranking, or repository access here.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from src.config.settings import get_app_settings
from src.shared.logging import get_logger

# from src.application.${FEATURE_LOWER}_use_case import ${FEATURE_TITLE}UseCase, ${FEATURE_TITLE}Request

logger = get_logger(__name__)
router = APIRouter(prefix="/${FEATURE_LOWER}", tags=["${FEATURE_LOWER}"])
templates = Jinja2Templates(directory="src/web/templates")


# ---------------------------------------------------------------------------
# Use-case dependency
# ---------------------------------------------------------------------------

# def get_${FEATURE_LOWER}_use_case() -> ${FEATURE_TITLE}UseCase:
#     settings = get_app_settings()
#     return ${FEATURE_TITLE}UseCase(...)
#
# ${FEATURE_TITLE}UseCaseDep = Annotated[${FEATURE_TITLE}UseCase, Depends(get_${FEATURE_LOWER}_use_case)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def ${FEATURE_LOWER}_page(
    request: Request,
    # use_case: ${FEATURE_TITLE}UseCaseDep,
) -> Response:
    """Full-page SSR route. Delegate to use case and render template."""
    # result = await use_case.execute(${FEATURE_TITLE}Request())
    return templates.TemplateResponse(
        request,
        "pages/${FEATURE_LOWER}.html",
        {"items": []},
    )


@router.get("/partial", response_class=HTMLResponse)
async def ${FEATURE_LOWER}_partial(
    request: Request,
    # use_case: ${FEATURE_TITLE}UseCaseDep,
) -> Response:
    """HTMX swap target — returns fragment only, not a full page."""
    # result = await use_case.execute(${FEATURE_TITLE}Request())
    return templates.TemplateResponse(
        request,
        "partials/${FEATURE_LOWER}_list.html",
        {"items": []},
    )


@router.post("/action", response_class=HTMLResponse)
async def ${FEATURE_LOWER}_action(
    request: Request,
    item_id: Annotated[str, Form()],
    # use_case: ${FEATURE_TITLE}UseCaseDep,
) -> Response:
    """
    Form action. Delegate to use case.
    - On success: redirect (303 See Other).
    - On failure: re-render form with error context (422).
    """
    logger.info("${FEATURE_LOWER}_action_requested", item_id=item_id)
    # result = await use_case.execute(${FEATURE_TITLE}Request(item_id=item_id))
    # if not result.success:
    #     return templates.TemplateResponse(
    #         request, "pages/${FEATURE_LOWER}.html", {"error": result.error}, status_code=422
    #     )
    return RedirectResponse(url="/${FEATURE_LOWER}", status_code=303)
EOF
