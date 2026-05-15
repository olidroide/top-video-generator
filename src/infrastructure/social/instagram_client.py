import asyncio
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Any

from src.config.settings import AppSettings, Environment, get_app_settings
from src.infrastructure.social.ssl_context_factory import configure_process_wide_certifi_bundle
from src.shared.logging import get_logger

logger = get_logger(__name__)


class InstagramLoginError(RuntimeError):
    """Raised when the Instagram client cannot authenticate."""


class InstagramDependencyError(RuntimeError):
    """Raised when the optional Instagram dependency is not installed."""


def _development_ssl_mode(settings: AppSettings) -> str:
    if settings.env == Environment.DEVELOPMENT and settings.use_certifi:
        return "development_certifi_and_bypass"
    return "default"


def is_instagrapi_available() -> bool:
    """Return whether the optional instagrapi dependency is installed."""
    return importlib.util.find_spec("instagrapi") is not None


def _import_instagram_client_types() -> tuple[type[Any], type[Exception]]:
    if not is_instagrapi_available():
        raise InstagramDependencyError(
            "instagrapi is not installed. Install the 'instagram' optional dependency to enable Instagram publishing."
        )

    instagrapi_module = importlib.import_module("instagrapi")
    exceptions_module = importlib.import_module("instagrapi.exceptions")
    return instagrapi_module.Client, exceptions_module.LoginRequired


def _configure_optional_certifi_for_development(settings: AppSettings) -> None:
    if settings.env != Environment.DEVELOPMENT or not settings.use_certifi:
        logger.debug(
            "instagram_client.certifi_not_enabled",
            env=settings.env,
            use_certifi=settings.use_certifi,
        )
        return

    cert_bundle = configure_process_wide_certifi_bundle(settings)
    if cert_bundle is None:
        return

    logger.info("instagram_client.certifi_enabled_for_development", cert_bundle=cert_bundle)


def _configure_optional_ssl_bypass_for_development(instagram_client_instance: Any, settings: AppSettings) -> None:
    if settings.env != Environment.DEVELOPMENT or not settings.use_certifi:
        logger.debug(
            "instagram_client.ssl_bypass_not_enabled",
            env=settings.env,
            use_certifi=settings.use_certifi,
        )
        return

    for session_name in ("private", "public"):
        session = getattr(instagram_client_instance, session_name, None)
        if session is not None and hasattr(session, "verify"):
            session.verify = False

    logger.warning("instagram_client.ssl_verify_disabled_for_development")


def _should_skip_session_timeline_probe(settings: AppSettings) -> bool:
    return settings.env == Environment.DEVELOPMENT and settings.use_certifi


def _configure_http_noise_reduction_for_development(settings: AppSettings) -> None:
    if settings.env != Environment.DEVELOPMENT:
        return

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logger.info("instagram_client.http_noise_reduction_enabled_for_development")


def _load_session(instagram_client_instance: Any, settings_file_path: Path) -> Any:
    try:
        logger.info("instagram_client.session_load_started", session_file=str(settings_file_path))
        session = instagram_client_instance.load_settings(settings_file_path)
        logger.info("instagram_client.session_load_finished", has_session=bool(session))
        return session
    except Exception as exc:  # noqa: BLE001
        logger.info("instagram_client.session_load_failed", error=str(exc))
        return None


def _try_auth_with_session(
    instagram_client_instance: Any,
    *,
    session: Any,
    settings: AppSettings,
    settings_file_path: Path,
    username: str | None,
    password: str | None,
    login_required_exception: type[Exception],
) -> bool:
    if not session:
        logger.info("instagram_client.session_missing_or_empty", session_file=str(settings_file_path))
        return False

    try:
        logger.info("instagram_client.session_login_started")
        instagram_client_instance.set_settings(session)
        instagram_client_instance.login(username, password)
        logger.info("instagram_client.session_login_succeeded")

        if _should_skip_session_timeline_probe(settings):
            logger.info("instagram_client.session_timeline_probe_skipped_for_development")
            return True

        try:
            logger.info("instagram_client.session_timeline_probe_started")
            instagram_client_instance.get_timeline_feed()
            logger.info("instagram_client.session_timeline_probe_succeeded")
            return True
        except login_required_exception:
            logger.info("Session is invalid, need to login via username and password")
            old_session = instagram_client_instance.get_settings()
            instagram_client_instance.set_settings({})
            instagram_client_instance.set_uuids(old_session["uuids"])
            logger.info("instagram_client.session_relogin_started")
            instagram_client_instance.login(username, password)
            instagram_client_instance.dump_settings(settings_file_path)
            logger.info("instagram_client.session_relogin_succeeded")
            return True
    except Exception as exc:  # noqa: BLE001
        logger.info("instagram_client.session_login_failed", error=str(exc))
        return False


def _try_auth_with_password(
    instagram_client_instance: Any,
    *,
    username: str | None,
    password: str | None,
    settings_file_path: Path,
) -> bool:
    try:
        logger.info(
            "instagram_client.password_login_started",
            username=username,
            reason="session_unavailable_or_failed",
        )
        if instagram_client_instance.login(username, password):
            instagram_client_instance.dump_settings(settings_file_path)
            logger.info("instagram_client.password_login_succeeded", session_file=str(settings_file_path))
            return True

        logger.warning("instagram_client.password_login_returned_false")
        return False
    except Exception as exc:  # noqa: BLE001
        logger.info("instagram_client.password_login_failed", error=str(exc))
        return False


def _get_instagram_client() -> Any:
    settings = get_app_settings()
    ssl_mode = _development_ssl_mode(settings)
    _configure_http_noise_reduction_for_development(settings)
    logger.info(
        "instagram_client.connection_bootstrap_started",
        env=settings.env,
        ssl_mode=ssl_mode,
        has_username=bool(settings.instagram_client_username),
        has_password=bool(settings.instagram_client_password),
        session_file=settings.instagram_client_session_file or "instagram_session.json",
    )
    _configure_optional_certifi_for_development(settings)

    username = settings.instagram_client_username
    password_secret = settings.instagram_client_password
    password = password_secret.get_secret_value() if password_secret else None
    settings_session_file = settings.instagram_client_session_file or "instagram_session.json"
    settings_file_path = Path(settings_session_file)

    instagrapi_client_lib, login_required_exception = _import_instagram_client_types()

    instagram_client_instance = instagrapi_client_lib()
    _configure_optional_ssl_bypass_for_development(instagram_client_instance, settings)
    logger.info(
        "instagram_client.client_initialized",
        ssl_mode=ssl_mode,
        session_file=str(settings_file_path),
    )
    session = _load_session(instagram_client_instance, settings_file_path)
    login_via_session = _try_auth_with_session(
        instagram_client_instance,
        session=session,
        settings=settings,
        settings_file_path=settings_file_path,
        username=username,
        password=password,
        login_required_exception=login_required_exception,
    )
    login_via_pw = False
    if not login_via_session:
        login_via_pw = _try_auth_with_password(
            instagram_client_instance,
            username=username,
            password=password,
            settings_file_path=settings_file_path,
        )

    if not login_via_pw and not login_via_session:
        logger.error(
            "instagram_client.connection_bootstrap_failed",
            ssl_mode=ssl_mode,
            used_session_path=bool(session),
            used_password_path=not login_via_session,
        )
        raise InstagramLoginError("Couldn't login user with either password or session")

    logger.info(
        "instagram_client.connection_bootstrap_succeeded",
        ssl_mode=ssl_mode,
        authenticated_via="session" if login_via_session else "password",
    )

    return instagram_client_instance


class InstagramClient:
    async def check_connection(self) -> bool:
        try:
            await asyncio.to_thread(_get_instagram_client)
            logger.info("instagram_client.connection_verified")
            return True
        except Exception as exc:
            logger.exception("instagram_client.connection_failed", error=str(exc))
            return False

    async def upload_video(self, video_path: str, caption: str) -> str | None:
        try:
            logger.info("instagram_client.upload_started", video_path=video_path, caption=caption)

            def _do_upload() -> Any:
                client = _get_instagram_client()
                return client.clip_upload(path=Path(video_path), caption=caption)

            media = await asyncio.to_thread(_do_upload)

            if media and hasattr(media, "pk"):
                logger.info("instagram_client.upload_succeeded", media_id=str(media.pk))
                return str(media.pk)
            if media and hasattr(media, "id"):
                logger.info("instagram_client.upload_succeeded", media_id=str(media.id))
                return str(media.id)
            logger.error("instagram_client.upload_missing_media_id")
            if media is not None:
                logger.debug("instagram_client.upload_returned_media", media=repr(media))
            else:
                logger.debug("instagram_client.upload_returned_none")
            return None
        except Exception as exc:
            logger.exception("instagram_client.upload_failed", error=str(exc))
            return None

    async def get_media_info(self, media_pk: str) -> Any | None:
        try:

            def _get_info() -> Any:
                client = _get_instagram_client()
                return client.media_info(media_pk)

            return await asyncio.to_thread(_get_info)
        except Exception as exc:
            logger.exception("instagram_client.media_info_failed", error=str(exc))
            return None
