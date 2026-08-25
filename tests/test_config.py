from __future__ import annotations

from src.config import Settings


def test_database_url_selects_persistent_database(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@example.test:5432/postgres?sslmode=require")
    settings = Settings.from_environment()

    assert settings.database_url == "postgresql://user:password@example.test:5432/postgres?sslmode=require"


def test_required_database_url_fails_fast_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REQUIRE_DATABASE_URL", "true")
    settings = Settings.from_environment()

    try:
        settings.validate_database_configuration()
    except ValueError as error:
        assert str(error) == "DATABASE_URL must be set for this run"
    else:
        raise AssertionError("expected a missing required database URL to fail")
