from __future__ import annotations

import logging
import os
from types import SimpleNamespace

from src.config.settings import Environment
from src.infrastructure.social.instagram_client import (
    _configure_http_noise_reduction_for_development,
    _configure_optional_certifi_for_development,
    _configure_optional_ssl_bypass_for_development,
    _should_skip_session_timeline_probe,
)


class _FakeSession:
    def __init__(self) -> None:
        self.verify = True


class _FakeInstagramClient:
    def __init__(self) -> None:
        self.private = _FakeSession()
        self.public = _FakeSession()


def test_configure_optional_certifi_for_development_sets_env(monkeypatch) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    fake_certifi = SimpleNamespace(where=lambda: "/tmp/certifi.pem")

    def _fake_import_module(name: str) -> object:
        if name == "certifi":
            return fake_certifi
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("src.infrastructure.social.instagram_client.importlib.import_module", _fake_import_module)

    settings = SimpleNamespace(
        env=Environment.DEVELOPMENT,
        instagram_dev_use_certifi=True,
    )

    _configure_optional_certifi_for_development(settings)

    assert os.environ["SSL_CERT_FILE"] == "/tmp/certifi.pem"
    assert os.environ["REQUESTS_CA_BUNDLE"] == "/tmp/certifi.pem"


def test_configure_optional_ssl_bypass_for_development_disables_verification() -> None:
    settings = SimpleNamespace(
        env=Environment.DEVELOPMENT,
        instagram_dev_use_certifi=True,
    )
    client = _FakeInstagramClient()

    _configure_optional_ssl_bypass_for_development(client, settings)

    assert client.private.verify is False
    assert client.public.verify is False


def test_configure_optional_ssl_bypass_skips_in_production() -> None:
    settings = SimpleNamespace(
        env=Environment.PRODUCTION,
        instagram_dev_use_certifi=True,
    )
    client = _FakeInstagramClient()

    _configure_optional_ssl_bypass_for_development(client, settings)

    assert client.private.verify is True
    assert client.public.verify is True


def test_should_skip_session_timeline_probe_in_development_flag_on() -> None:
    settings = SimpleNamespace(
        env=Environment.DEVELOPMENT,
        instagram_dev_use_certifi=True,
    )

    assert _should_skip_session_timeline_probe(settings) is True


def test_should_not_skip_session_timeline_probe_in_production() -> None:
    settings = SimpleNamespace(
        env=Environment.PRODUCTION,
        instagram_dev_use_certifi=True,
    )

    assert _should_skip_session_timeline_probe(settings) is False


def test_configure_http_noise_reduction_for_development_sets_warning_levels() -> None:
    urllib3_logger = logging.getLogger("urllib3")
    urllib3_cp_logger = logging.getLogger("urllib3.connectionpool")
    requests_logger = logging.getLogger("requests")

    prev_urllib3 = urllib3_logger.level
    prev_urllib3_cp = urllib3_cp_logger.level
    prev_requests = requests_logger.level
    try:
        settings = SimpleNamespace(env=Environment.DEVELOPMENT)

        _configure_http_noise_reduction_for_development(settings)

        assert urllib3_logger.level == logging.WARNING
        assert urllib3_cp_logger.level == logging.WARNING
        assert requests_logger.level == logging.WARNING
    finally:
        urllib3_logger.setLevel(prev_urllib3)
        urllib3_cp_logger.setLevel(prev_urllib3_cp)
        requests_logger.setLevel(prev_requests)


def test_configure_http_noise_reduction_for_development_skips_in_production() -> None:
    urllib3_logger = logging.getLogger("urllib3")
    prev_urllib3 = urllib3_logger.level
    try:
        urllib3_logger.setLevel(logging.INFO)
        settings = SimpleNamespace(env=Environment.PRODUCTION)

        _configure_http_noise_reduction_for_development(settings)

        assert urllib3_logger.level == logging.INFO
    finally:
        urllib3_logger.setLevel(prev_urllib3)
