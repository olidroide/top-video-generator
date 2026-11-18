import os

import pytest

TEST_APP_SECRET = "test-session-secret-with-at-least-32-characters"
os.environ["TOP_MUSIC_APP_SECRET_KEY"] = TEST_APP_SECRET
os.environ["TOP_MUSIC_ENV"] = "development"


@pytest.fixture(autouse=True)
def test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_APP_SECRET_KEY", TEST_APP_SECRET)
    monkeypatch.setenv("TOP_MUSIC_ENV", "development")
