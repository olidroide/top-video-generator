from instagrapi import Client as InstagrapiClientLib  # type: ignore
from instagrapi.exceptions import LoginRequired  # type: ignore

from src.logger import get_logger
from src.settings import get_app_settings

logger = get_logger(__name__)


def _get_instagram_client():
    USERNAME = get_app_settings().instagram_client_username
    PASSWORD = get_app_settings().instagram_client_password
    settings_filename = get_app_settings().instagram_client_session_file

    instagram_client_instance = InstagrapiClientLib()
    login_via_session = False
    login_via_pw = False
    session = None

    try:
        session = instagram_client_instance.load_settings(settings_filename)
    except Exception as e:
        logger.info("Couldn't get session information: %s" % e)

    if session:
        try:
            instagram_client_instance.set_settings(session)
            instagram_client_instance.login(USERNAME, PASSWORD)

            try:
                instagram_client_instance.get_timeline_feed()
            except LoginRequired:
                logger.info("Session is invalid, need to login via username and password")
                old_session = instagram_client_instance.get_settings()
                instagram_client_instance.set_settings({})
                instagram_client_instance.set_uuids(old_session["uuids"])
                instagram_client_instance.login(USERNAME, PASSWORD)
                instagram_client_instance.dump_settings(settings_filename)
            login_via_session = True
        except Exception as e:
            logger.info("Couldn't login user using session information: %s" % e)

    if not login_via_session:
        try:
            logger.info("Attempting to login via username and password. username: %s" % USERNAME)
            if instagram_client_instance.login(USERNAME, PASSWORD):
                login_via_pw = True
                instagram_client_instance.dump_settings(settings_filename)
        except Exception as e:
            logger.info("Couldn't login user using username and password: %s" % e)

    if not login_via_pw and not login_via_session:
        raise Exception("Couldn't login user with either password or session")

    return instagram_client_instance


class InstagramClient:
    async def upload_video(self, video_path: str, caption: str) -> str | None:
        """
        Sube un vídeo a Instagram como un Reel usando instagrapi.
        """
        try:
            logger.info(f"Intentando subir Reel desde la ruta: {video_path} con caption: '{caption}'")
            client = _get_instagram_client()
            media = client.clip_upload(path=video_path, caption=caption)

            if media and hasattr(media, "pk"):
                logger.info(f"Reel subido exitosamente a Instagram. Media ID: {media.pk}")
                return str(media.pk)
            elif media and hasattr(media, "id"):
                logger.info(f"Reel subido exitosamente a Instagram. Media ID: {media.id}")
                return str(media.id)
            else:
                logger.error("La subida del Reel a Instagram no devolvió un objeto media con 'pk' o 'id'.")
                if media is not None:
                    logger.debug(f"Objeto media devuelto: {repr(media)}")
                else:
                    logger.debug("instagrapi.clip_upload devolvió None.")
                return None
        except Exception as e:
            logger.error(f"Excepción durante la subida del Reel a Instagram: {e}", exc_info=True)
            return None
