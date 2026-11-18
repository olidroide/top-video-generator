"""Session-bound CSRF helpers for web mutations."""

from __future__ import annotations

import hmac
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

_CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    """Get or create the session-bound CSRF token."""
    token = request.session.get(_CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[_CSRF_SESSION_KEY] = token
    return token


def is_valid_csrf_token(request: Request, submitted_token: str | None) -> bool:
    """Validate a submitted token against the signed session state."""
    if not submitted_token:
        return False
    expected = request.session.get(_CSRF_SESSION_KEY)
    if not isinstance(expected, str) or not expected:
        return False
    return hmac.compare_digest(submitted_token, expected)
