"""JWT secret resolution: production must never run on the dev default."""
from __future__ import annotations

import pytest

from dependencies.auth import _DEV_FALLBACK_SECRET, _resolve_secret_key


def test_production_missing_secret_is_fatal(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be set"):
        _resolve_secret_key()


def test_production_dev_default_is_fatal(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", _DEV_FALLBACK_SECRET)
    with pytest.raises(RuntimeError, match="development default"):
        _resolve_secret_key()


def test_production_short_secret_is_fatal(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")
    with pytest.raises(RuntimeError, match="shorter"):
        _resolve_secret_key()


def test_production_strong_secret_accepted(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 48)
    assert _resolve_secret_key() == "x" * 48


def test_dev_falls_back_with_warning(monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    assert _resolve_secret_key() == _DEV_FALLBACK_SECRET


def test_dev_env_secret_wins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "my-local-secret")
    assert _resolve_secret_key() == "my-local-secret"
