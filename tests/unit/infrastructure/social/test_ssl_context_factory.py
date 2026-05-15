from __future__ import annotations

import os
import ssl
from types import SimpleNamespace

from src.config.settings import Environment
from src.infrastructure.social.ssl_context_factory import build_ssl_context


class _FakeSSLContext:
    def __init__(self) -> None:
        self.loaded_cafile: str | None = None

    def load_verify_locations(self, *, cafile: str) -> None:
        self.loaded_cafile = cafile


def test_build_ssl_context_uses_default_context_without_certifi(monkeypatch) -> None:
    fake_context = _FakeSSLContext()
    monkeypatch.setattr(ssl, "create_default_context", lambda: fake_context)
    settings = SimpleNamespace(env=Environment.PRODUCTION, use_certifi=True, ca_bundle_file=None)

    context = build_ssl_context(settings)

    assert context is fake_context
    assert fake_context.loaded_cafile is None


def test_build_ssl_context_loads_certifi_bundle_in_development(monkeypatch) -> None:
    fake_context = _FakeSSLContext()
    monkeypatch.setattr(ssl, "create_default_context", lambda: fake_context)

    fake_certifi = SimpleNamespace(where=lambda: "/tmp/certifi.pem")

    def _fake_import_module(name: str) -> object:
        if name == "certifi":
            return fake_certifi
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("src.infrastructure.social.ssl_context_factory.importlib.import_module", _fake_import_module)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    settings = SimpleNamespace(env=Environment.DEVELOPMENT, use_certifi=True, ca_bundle_file=None)

    context = build_ssl_context(settings)

    assert context is fake_context
    assert fake_context.loaded_cafile == "/tmp/certifi.pem"
    assert os.environ["SSL_CERT_FILE"] == "/tmp/certifi.pem"
    assert os.environ["REQUESTS_CA_BUNDLE"] == "/tmp/certifi.pem"


def test_build_ssl_context_prefers_custom_ca_bundle(monkeypatch) -> None:
    fake_context = _FakeSSLContext()
    monkeypatch.setattr(ssl, "create_default_context", lambda: fake_context)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    settings = SimpleNamespace(
        env=Environment.DEVELOPMENT,
        use_certifi=True,
        ca_bundle_file="/tmp/custom-ca.pem",
    )

    context = build_ssl_context(settings)

    assert context is fake_context
    assert fake_context.loaded_cafile == "/tmp/custom-ca.pem"
    assert os.environ["SSL_CERT_FILE"] == "/tmp/custom-ca.pem"
    assert os.environ["REQUESTS_CA_BUNDLE"] == "/tmp/custom-ca.pem"
