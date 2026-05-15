from __future__ import annotations

import importlib
import os
import ssl

from src.config.settings import AppSettings, Environment
from src.shared.logging import get_logger

logger = get_logger(__name__)


def _use_certifi_in_development(settings: AppSettings) -> bool:
    return settings.env == Environment.DEVELOPMENT and settings.use_certifi


def configure_process_wide_certifi_bundle(settings: AppSettings) -> str | None:
    """Set process-wide CA bundle env vars so non-aiohttp clients share same trust bundle."""
    cert_bundle = settings.ca_bundle_file
    if cert_bundle:
        os.environ["SSL_CERT_FILE"] = cert_bundle
        os.environ["REQUESTS_CA_BUNDLE"] = cert_bundle
        logger.info(
            "ssl_context.process_wide_custom_ca_enabled",
            cert_bundle=cert_bundle,
        )
        return cert_bundle

    if not _use_certifi_in_development(settings):
        return None

    try:
        certifi = importlib.import_module("certifi")
        cert_bundle = certifi.where()
        os.environ["SSL_CERT_FILE"] = cert_bundle
        os.environ["REQUESTS_CA_BUNDLE"] = cert_bundle
        logger.info(
            "ssl_context.process_wide_certifi_enabled_for_development",
            cert_bundle=cert_bundle,
        )
        return cert_bundle
    except Exception as exc:  # noqa: BLE001
        logger.info("ssl_context.certifi_unavailable", error=str(exc))
        return None


def build_ssl_context(settings: AppSettings) -> ssl.SSLContext:
    """Build strict SSL context and load extra CA bundle in development when enabled."""
    context = ssl.create_default_context()
    cert_bundle = configure_process_wide_certifi_bundle(settings)

    if cert_bundle is None:
        return context

    context.load_verify_locations(cafile=cert_bundle)
    logger.info(
        "ssl_context.certifi_enabled_for_development",
        cert_bundle=cert_bundle,
    )

    return context
