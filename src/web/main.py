from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config.settings import AppSettings, get_app_settings
from src.web.routes.admin import router as admin_router
from src.web.routes.auth import router as auth_router
from src.web.routes.ops import router as ops_router
from src.web.routes.pages import router as pages_router
from src.web.state import WEB_DIR


def create_app(settings: AppSettings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else get_app_settings()
    app = FastAPI()
    app.state.settings = resolved_settings
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(pages_router)
    app.include_router(ops_router)

    app.add_middleware(
        SessionMiddleware,
        secret_key=resolved_settings.app_secret_key or "dev-secret",
    )

    return app
