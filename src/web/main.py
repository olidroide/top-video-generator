import secrets

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config.settings import AppSettings, get_app_settings
from src.web.routes.admin import router as admin_router
from src.web.routes.auth import router as auth_router
from src.web.routes.ops import router as ops_router
from src.web.routes.pages import router as pages_router
from src.web.state import WEB_DIR

_MIN_APP_SECRET_LENGTH = 32


def create_app(settings: AppSettings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else get_app_settings()
    secret_key = resolved_settings.app_secret_key
    if not secret_key:
        if resolved_settings.is_production_env:
            raise RuntimeError("TOP_MUSIC_APP_SECRET_KEY is required when TOP_MUSIC_ENV=production")
        secret_key = secrets.token_urlsafe(_MIN_APP_SECRET_LENGTH)
    if resolved_settings.is_production_env and len(secret_key) < _MIN_APP_SECRET_LENGTH:
        raise RuntimeError("TOP_MUSIC_APP_SECRET_KEY must be at least 32 characters")

    app = FastAPI()
    app.state.settings = resolved_settings
    app.state.revoked_admin_sessions = set()
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(pages_router)
    app.include_router(ops_router)

    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        https_only=resolved_settings.is_production_env,
        same_site="lax",
        max_age=60 * 60 * 24 * 14,
    )

    return app
