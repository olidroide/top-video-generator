from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from src.config.settings import AppSettings, get_app_settings
from src.infrastructure.storage.auth_repository import AuthenticationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


def is_tiktok_uploader_available() -> bool:
    return find_spec("tiktok_uploader") is not None


class TikTokUploaderClient:
    """Thin wrapper for tiktok-uploader with cookie-based authentication."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        resolved_settings = settings if settings is not None else get_app_settings()
        self._db_auth_file = resolved_settings.db_auth_file
        self._tiktok_user_openid = resolved_settings.tiktok_user_openid or "default"
        self._tiktok_cookies_file = resolved_settings.tiktok_cookies_file
        self._tiktok_browser = resolved_settings.tiktok_browser

    def has_credentials(self) -> bool:
        return self._resolve_cookies_argument() is not None

    def check_connection(self) -> bool:
        """Best-effort local check: dependency + cookie presence + uploader init."""
        cookies = self._resolve_cookies_argument()
        if not cookies:
            return False
        self._build_uploader(cookies)
        return True

    def upload_video(self, file_path: str, caption: str) -> str | None:
        cookies = self._resolve_cookies_argument()
        if not cookies:
            raise RuntimeError(
                "TikTok cookies are not configured. Set TOP_MUSIC_TIKTOK_COOKIES_FILE or reconnect TikTok credentials."
            )

        if not self._has_valid_session(cookies):
            raise RuntimeError(
                "TikTok session expired. Cookies file exists but sessionid is missing or invalid. "
                "Re-export cookies from a logged-in TikTok browser session."
            )

        uploader = self._build_uploader(cookies)
        upload_result = self._call_upload(uploader, file_path=file_path, caption=caption)

        if isinstance(upload_result, str):
            return upload_result
        if isinstance(upload_result, dict):
            candidate = upload_result.get("video_id") or upload_result.get("publish_id") or upload_result.get("id")
            return str(candidate) if candidate else None
        return None

    def _resolve_cookies_argument(self) -> str | None:
        if self._tiktok_cookies_file:
            cookie_file = Path(self._tiktok_cookies_file)
            if not cookie_file.exists():
                logger.warning("tiktok.cookies_file_missing", path=str(cookie_file))
                return None
            return str(cookie_file)

        repo = AuthenticationRepository(Path(self._db_auth_file))
        auth = repo.get_tiktok_auth(self._tiktok_user_openid)
        if auth and auth.token:
            # During migration we allow existing auth token field to hold cookie payload.
            return auth.token
        return None

    @staticmethod
    def _has_valid_session(cookies_source: str) -> bool:
        """Check if cookies file contains a non-empty sessionid cookie."""
        try:
            cookie_path = Path(cookies_source)
            if not cookie_path.exists():
                return False
            content = cookie_path.read_text()
            sessionid_col = 5
            value_col = 6
            for line in content.splitlines():
                parts = line.split("\t")
                if len(parts) > value_col and parts[sessionid_col] == "sessionid" and parts[value_col].strip():
                    return True
            logger.warning("tiktok.sessionid_missing_in_cookies")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("tiktok.session_check_failed", error=str(exc))
            return False

    def _build_uploader(self, cookies: str) -> Any:
        if not is_tiktok_uploader_available():
            raise RuntimeError(
                "TikTok uploader dependency is missing. Install with: uv sync --all-groups --extra tiktok"
            )

        tiktok_uploader_class = self._resolve_uploader_class()

        try:
            return tiktok_uploader_class(cookies=cookies, browser=self._tiktok_browser, headless=True)
        except TypeError:
            try:
                return tiktok_uploader_class(cookies=cookies, headless=True)
            except TypeError:
                return tiktok_uploader_class(cookies=cookies)

    @staticmethod
    def _resolve_uploader_class() -> type[Any]:
        candidates = (
            ("tiktok_uploader", "TikTokUploader"),
            ("tiktok_uploader.uploader", "TikTokUploader"),
            ("tiktok_uploader.upload", "TikTokUploader"),
        )

        for module_name, class_name in candidates:
            try:
                module = import_module(module_name)
                uploader_class = getattr(module, class_name, None)
                if isinstance(uploader_class, type):
                    return uploader_class
            except ModuleNotFoundError:
                continue

        raise RuntimeError(
            "TikTok uploader package is installed but TikTokUploader class was not found. "
            "Please check the installed tiktok-uploader version."
        )

    @staticmethod
    def _call_upload(uploader: Any, *, file_path: str, caption: str) -> Any:
        upload_method = getattr(uploader, "upload_video", None)
        if upload_method is None:
            raise RuntimeError("TikTokUploader does not expose an upload_video method.")

        call_patterns: tuple[tuple[tuple[Any, ...], dict[str, Any]], ...] = (
            ((file_path,), {"description": caption}),
            ((file_path,), {"caption": caption}),
            ((file_path, caption), {}),
            ((), {"video": file_path, "description": caption}),
        )

        last_error: TypeError | None = None
        for args, kwargs in call_patterns:
            try:
                return upload_method(*args, **kwargs)
            except TypeError as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise RuntimeError("Unable to call TikTok uploader with supported upload signatures.") from last_error

        raise RuntimeError("Unable to call TikTok uploader upload method.")
