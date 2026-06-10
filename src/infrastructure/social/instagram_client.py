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


def _import_instagram_client_types() -> tuple[
    type[Any],
    type[Exception],
    type[Exception],
    type[Exception],
    type[Exception],
    type[Exception],
    type[Exception],
    type[Any],
]:
    if not is_instagrapi_available():
        raise InstagramDependencyError(
            "instagrapi is not installed. Install the 'instagram' optional dependency to enable Instagram publishing."
        )

    instagrapi_module = importlib.import_module("instagrapi")
    exceptions_module = importlib.import_module("instagrapi.exceptions")
    challenge_module = importlib.import_module("instagrapi.mixins.challenge")
    return (
        instagrapi_module.Client,
        exceptions_module.LoginRequired,
        exceptions_module.ClipNotUpload,
        exceptions_module.ClientThrottledError,
        exceptions_module.PleaseWaitFewMinutes,
        exceptions_module.FeedbackRequired,
        exceptions_module.ChallengeRequired,
        challenge_module.ChallengeChoice,
    )


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


def _configure_delay_range(instagram_client_instance: Any) -> None:
    instagram_client_instance.delay_range = [1, 3]
    logger.debug("instagram_client.delay_range_configured", min_delay=1, max_delay=3)


def _configure_challenge_handler(instagram_client_instance: Any) -> None:
    def challenge_code_handler(user: str, choice: Any) -> str:
        channel = getattr(choice, "name", str(choice))
        logger.warning(
            "instagram_client.challenge_required",
            username=user,
            channel=channel,
            message=f"Instagram requires verification via {channel}. Check your {channel.lower()} for a 6-digit code.",
        )
        return ""

    instagram_client_instance.challenge_code_handler = challenge_code_handler
    logger.debug("instagram_client.challenge_handler_configured")


def _load_session(instagram_client_instance: Any, settings_file_path: Path) -> Any:
    try:
        if not settings_file_path.exists():
            logger.info("instagram_client.session_file_not_found", session_file=str(settings_file_path))
            return None

        logger.info("instagram_client.session_load_started", session_file=str(settings_file_path))
        session = instagram_client_instance.load_settings(settings_file_path)
        logger.info("instagram_client.session_load_succeeded", has_session=bool(session))
        return session
    except Exception as exc:  # noqa: BLE001
        logger.warning("instagram_client.session_load_failed", error=str(exc), session_file=str(settings_file_path))
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
    """Validate loaded session and optionally re-authenticate if expired."""
    if not session:
        logger.info("instagram_client.session_missing_or_empty", session_file=str(settings_file_path))
        return False

    # In dev mode with certifi, assume session is valid
    if _should_skip_session_timeline_probe(settings):
        logger.info("instagram_client.session_timeline_probe_skipped_for_development")
        return True

    # Validate session by checking timeline feed
    logger.info("instagram_client.session_auth_started")
    try:
        logger.info("instagram_client.session_validation_started")
        instagram_client_instance.get_timeline_feed()
        logger.info("instagram_client.session_validation_succeeded")
        return True
    except login_required_exception as exc:
        # Session expired, need to re-authenticate
        logger.info("instagram_client.session_expired_reauth_required", reason=str(exc))
        return _reauth_with_password(
            instagram_client_instance,
            username=username,
            password=password,
            settings_file_path=settings_file_path,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("instagram_client.session_auth_failed", error=str(exc))
        return False


def _reauth_with_password(
    instagram_client_instance: Any,
    *,
    username: str | None,
    password: str | None,
    settings_file_path: Path,
    settings: AppSettings | None = None,
) -> bool:
    """Re-authenticate with password after session expires."""
    try:
        logger.info("instagram_client.password_reauth_started")
        verification_code = _get_totp_code(settings) if settings else None
        if verification_code:
            instagram_client_instance.login(username, password, verification_code=verification_code)
        else:
            instagram_client_instance.login(username, password)
        try:
            instagram_client_instance.dump_settings(settings_file_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "instagram_client.session_persist_failed",
                error=str(exc),
                session_file=str(settings_file_path),
            )
        logger.info("instagram_client.password_reauth_succeeded", session_file=str(settings_file_path))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("instagram_client.password_reauth_failed", error=str(exc))
        return False


def _try_auth_with_password(
    instagram_client_instance: Any,
    *,
    username: str | None,
    password: str | None,
    settings_file_path: Path,
    settings: AppSettings | None = None,
) -> bool:
    """Authenticate with password when no valid session exists."""
    try:
        logger.info(
            "instagram_client.password_login_started",
            username=username,
            reason="session_unavailable_or_failed",
        )
        verification_code = _get_totp_code(settings) if settings else None
        if verification_code:
            result = instagram_client_instance.login(username, password, verification_code=verification_code)
        else:
            result = instagram_client_instance.login(username, password)
        if result:
            try:
                instagram_client_instance.dump_settings(settings_file_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "instagram_client.session_persist_failed",
                    error=str(exc),
                    session_file=str(settings_file_path),
                )
            logger.info("instagram_client.password_login_succeeded", session_file=str(settings_file_path))
            return True

        logger.warning("instagram_client.password_login_returned_false")
        return False
    except Exception as exc:  # noqa: BLE001
        # Log the full exception type for diagnostics
        exc_type = type(exc).__name__
        logger.warning(
            "instagram_client.password_login_failed",
            error=str(exc),
            error_type=exc_type,
            session_file=str(settings_file_path),
        )
        return False


def _get_totp_code(settings: AppSettings) -> str | None:
    """Generate TOTP code if seed is configured."""
    totp_seed_secret = getattr(settings, "instagram_client_totp_seed", None)
    if not totp_seed_secret:
        return None

    try:
        import pyotp

        seed = totp_seed_secret.get_secret_value()
        code = pyotp.TOTP(seed).now()
        logger.debug("instagram_client.totp_code_generated")
        return code
    except ImportError:
        logger.warning("instagram_client.totp_pyotp_missing", message="pyotp not installed, TOTP disabled")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("instagram_client.totp_generation_failed", error=str(exc))
        return None


def _get_client_with_fresh_login() -> Any:
    settings = get_app_settings()
    ssl_mode = _development_ssl_mode(settings)
    _configure_http_noise_reduction_for_development(settings)
    _configure_optional_certifi_for_development(settings)

    username = settings.instagram_client_username
    password_secret = settings.instagram_client_password
    password = password_secret.get_secret_value() if password_secret else None
    settings_session_file = settings.instagram_client_session_file or "instagram_session.json"
    settings_file_path = Path(settings_session_file)

    instagrapi_client_lib, _, _, _, _, _, _, _ = _import_instagram_client_types()
    client = instagrapi_client_lib()
    _configure_optional_ssl_bypass_for_development(client, settings)
    _configure_delay_range(client)
    _configure_challenge_handler(client)

    old_uuids = None
    if settings_file_path.exists():
        try:
            old_session = client.load_settings(settings_file_path)
            if old_session and "uuids" in old_session:
                old_uuids = old_session["uuids"]
                logger.debug("instagram_client.preserved_device_uuids", uuid_count=len(old_uuids))
        except Exception as exc:  # noqa: BLE001
            logger.warning("instagram_client.load_old_session_failed", error=str(exc))

    if old_uuids:
        client.set_settings({})
        client.set_uuids(old_uuids)

    logger.info("instagram_client.fresh_login_started", ssl_mode=ssl_mode, preserved_uuids=bool(old_uuids))

    verification_code = _get_totp_code(settings)
    if verification_code:
        client.login(username, password, verification_code=verification_code)
    else:
        client.login(username, password)

    try:
        client.dump_settings(settings_file_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("instagram_client.session_persist_failed", error=str(exc))
    logger.info("instagram_client.fresh_login_succeeded")
    return client


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

    instagrapi_client_lib, login_required_exception, _, _, _, _, _, _ = _import_instagram_client_types()

    instagram_client_instance = instagrapi_client_lib()
    _configure_optional_ssl_bypass_for_development(instagram_client_instance, settings)
    _configure_delay_range(instagram_client_instance)
    _configure_challenge_handler(instagram_client_instance)
    logger.info(
        "instagram_client.client_initialized",
        ssl_mode=ssl_mode,
        session_file=str(settings_file_path),
        session_file_exists=settings_file_path.exists(),
    )

    session = _load_session(instagram_client_instance, settings_file_path)
    logger.info(
        "instagram_client.session_load_completed",
        session_exists=bool(session),
        session_file=str(settings_file_path),
    )

    login_via_session = _try_auth_with_session(
        instagram_client_instance,
        session=session,
        settings=settings,
        settings_file_path=settings_file_path,
        username=username,
        password=password,
        login_required_exception=login_required_exception,
    )
    logger.info(
        "instagram_client.session_auth_result",
        success=login_via_session,
        auth_method="session",
    )

    login_via_pw = False
    if not login_via_session:
        login_via_pw = _try_auth_with_password(
            instagram_client_instance,
            username=username,
            password=password,
            settings_file_path=settings_file_path,
            settings=settings,
        )
        logger.info(
            "instagram_client.password_auth_result",
            success=login_via_pw,
            auth_method="password",
        )

    if not login_via_pw and not login_via_session:
        logger.error(
            "instagram_client.connection_bootstrap_failed",
            ssl_mode=ssl_mode,
            session_was_available=bool(session),
            session_auth_tried=True,
            session_auth_succeeded=login_via_session,
            password_auth_tried=True,
            password_auth_succeeded=login_via_pw,
        )
        raise InstagramLoginError(
            "Couldn't login user with either password or session. "
            f"Verify credentials and ensure session file is writable: {settings_file_path}"
        )

    logger.info(
        "instagram_client.connection_bootstrap_succeeded",
        ssl_mode=ssl_mode,
        authenticated_via="session" if login_via_session else "password",
        session_file=str(settings_file_path),
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

            def _do_upload_with_normal_client() -> Any:
                client = _get_instagram_client()
                return client.clip_upload(path=Path(video_path), caption=caption)

            media = await asyncio.to_thread(_do_upload_with_normal_client)
            return self._extract_media_id(media)
        except Exception as exc:
            error_type = self._classify_error(exc)
            logger.warning("instagram_client.upload_error_classified", error_type=error_type, error=str(exc))

            if error_type == "login_required":
                return await self._retry_upload_with_fresh_login(video_path, caption)
            if error_type == "throttled":
                return await self._retry_upload_with_backoff(video_path, caption)
            if error_type in ("please_wait", "feedback_required", "challenge_required"):
                logger.exception("instagram_client.upload_blocked_no_retry", error=str(exc))
                return None
            logger.exception("instagram_client.upload_failed", error=str(exc))
            return None

    def _classify_error(self, exc: Exception) -> str:
        exc_type = type(exc).__name__
        error_msg = str(exc).lower()

        type_mapping = {
            "LoginRequired": "login_required",
            "ClipNotUpload": "login_required",
            "ClientThrottledError": "throttled",
            "PleaseWaitFewMinutes": "please_wait",
            "FeedbackRequired": "feedback_required",
            "ChallengeRequired": "challenge_required",
        }

        if exc_type in type_mapping:
            return type_mapping[exc_type]

        msg_patterns = [
            ("login_required", "login"),
            ("throttled", "429", "throttl"),
            ("please_wait", "please wait", "wait few minutes"),
            ("feedback_required", "feedback"),
            ("challenge_required", "challenge"),
        ]

        for error_class, *patterns in msg_patterns:
            if any(pattern in error_msg for pattern in patterns):
                return error_class

        return "unknown"

    async def _retry_upload_with_fresh_login(self, video_path: str, caption: str) -> str | None:
        logger.warning("instagram_client.upload_session_expired_retrying")
        try:
            media = await asyncio.to_thread(self._upload_with_fresh_login, video_path, caption)
            return self._extract_media_id(media)
        except Exception as retry_exc:
            logger.exception("instagram_client.upload_retry_failed", error=str(retry_exc))
            return None

    async def _retry_upload_with_backoff(self, video_path: str, caption: str) -> str | None:
        backoff_seconds = 30
        logger.warning("instagram_client.upload_throttled_backing_off", seconds=backoff_seconds)
        await asyncio.sleep(backoff_seconds)
        try:
            media = await asyncio.to_thread(self._upload_with_fresh_login, video_path, caption)
            return self._extract_media_id(media)
        except Exception as retry_exc:
            logger.exception("instagram_client.upload_backoff_retry_failed", error=str(retry_exc))
            return None

    def _upload_with_fresh_login(self, video_path: str, caption: str) -> Any:
        client = _get_client_with_fresh_login()
        return client.clip_upload(path=Path(video_path), caption=caption)

    def _extract_media_id(self, media: Any) -> str | None:
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

    async def get_media_info(self, media_pk: str) -> Any | None:
        try:

            def _get_info() -> Any:
                client = _get_instagram_client()
                return client.media_info(media_pk)

            return await asyncio.to_thread(_get_info)
        except Exception as exc:
            logger.exception("instagram_client.media_info_failed", error=str(exc))
            return None
