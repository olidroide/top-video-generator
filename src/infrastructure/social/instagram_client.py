import asyncio
from pathlib import Path
from typing import Any

from instagrapi import Client as InstagrapiClientLib
from instagrapi.exceptions import LoginRequired

from src.config.settings import get_app_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)


class InstagramLoginError(RuntimeError):
    """Raised when the Instagram client cannot authenticate."""


def _get_instagram_client() -> InstagrapiClientLib:
    username = get_app_settings().instagram_client_username
    password = get_app_settings().instagram_client_password
    settings_session_file = get_app_settings().instagram_client_session_file or "instagram_session.json"
    settings_file_path = Path(settings_session_file)

    instagram_client_instance = InstagrapiClientLib()
    login_via_session = False
    login_via_pw = False
    session = None

    try:
        session = instagram_client_instance.load_settings(settings_file_path)
    except Exception as exc:  # noqa: BLE001
        logger.info("instagram_client.session_load_failed", error=str(exc))

    if session:
        try:
            instagram_client_instance.set_settings(session)
            instagram_client_instance.login(username, password)

            try:
                instagram_client_instance.get_timeline_feed()
            except LoginRequired:
                logger.info("Session is invalid, need to login via username and password")
                old_session = instagram_client_instance.get_settings()
                instagram_client_instance.set_settings({})
                instagram_client_instance.set_uuids(old_session["uuids"])
                instagram_client_instance.login(username, password)
                instagram_client_instance.dump_settings(settings_file_path)
            login_via_session = True
        except Exception as exc:  # noqa: BLE001
            logger.info("instagram_client.session_login_failed", error=str(exc))

    if not login_via_session:
        try:
            logger.info("Attempting to login via username and password", username=username)
            if instagram_client_instance.login(username, password):
                login_via_pw = True
                instagram_client_instance.dump_settings(settings_file_path)
        except Exception as exc:  # noqa: BLE001
            logger.info("instagram_client.password_login_failed", error=str(exc))

    if not login_via_pw and not login_via_session:
        raise InstagramLoginError("Couldn't login user with either password or session")

    return instagram_client_instance


class InstagramClient:
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
