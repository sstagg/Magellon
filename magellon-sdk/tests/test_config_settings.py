"""Shared-settings tests.

Covers YAML/JSON round-trips and the class-keyed singleton registry.
Each singleton test defines its own ``BaseAppSettingsSingleton``
subclass so isolation is by class identity — no shared registry state
needs to be cleared.
"""
from __future__ import annotations

import os
from typing import Optional

import pytest

from magellon_sdk.config import (
    BaseAppSettings,
    BaseAppSettingsSingleton,
    RabbitMQSettings,
)


class _ExtendedSettings(BaseAppSettings):
    JOBS_DIR: Optional[str] = None
    CUSTOM_FLAG: bool = False


def test_base_app_settings_accepts_nested_rabbitmq():
    s = BaseAppSettings(rabbitmq_settings=RabbitMQSettings(HOST_NAME="rmq", PORT=5673))
    assert s.rabbitmq_settings.HOST_NAME == "rmq"
    assert s.rabbitmq_settings.PORT == 5673


def test_yaml_round_trip(tmp_path):
    settings = _ExtendedSettings(
        JOBS_DIR="/var/jobs",
        CUSTOM_FLAG=True,
        rabbitmq_settings=RabbitMQSettings(HOST_NAME="rmq", USER_NAME="u"),
    )
    target = tmp_path / "settings.yml"
    settings.save_yaml_settings(str(target))

    loaded = _ExtendedSettings.load_yaml_file_settings(str(target))
    assert isinstance(loaded, _ExtendedSettings)
    assert loaded.JOBS_DIR == "/var/jobs"
    assert loaded.CUSTOM_FLAG is True
    assert loaded.rabbitmq_settings.HOST_NAME == "rmq"
    assert loaded.rabbitmq_settings.USER_NAME == "u"


def test_load_yaml_file_missing_returns_none(tmp_path):
    assert _ExtendedSettings.load_yaml_file_settings(str(tmp_path / "nope.yml")) is None


def test_load_yaml_settings_from_string():
    yaml_text = (
        "JOBS_DIR: /tmp/j\n"
        "CUSTOM_FLAG: true\n"
        "rabbitmq_settings:\n"
        "  HOST_NAME: rmq\n"
    )
    loaded = _ExtendedSettings.load_yaml_settings(yaml_text)
    assert isinstance(loaded, _ExtendedSettings)
    assert loaded.JOBS_DIR == "/tmp/j"
    assert loaded.rabbitmq_settings.HOST_NAME == "rmq"


def test_load_yaml_settings_invalid_yaml_returns_none():
    assert _ExtendedSettings.load_yaml_settings("::::not yaml:::: [") is None


def test_json_round_trip(tmp_path):
    settings = _ExtendedSettings(JOBS_DIR="/a/b")
    target = tmp_path / "settings.json"
    settings.save_settings_to_json_file(str(target))

    loaded = _ExtendedSettings.load_json_file_settings(str(target))
    assert isinstance(loaded, _ExtendedSettings)
    assert loaded.JOBS_DIR == "/a/b"


def test_load_json_file_missing_returns_none(tmp_path):
    assert _ExtendedSettings.load_json_file_settings(str(tmp_path / "nope.json")) is None


def test_singleton_requires_settings_class():
    class _Unbound(BaseAppSettingsSingleton):
        _dev_yaml = "./never-exists-dev.yml"
        _prod_yaml = "./never-exists-prod.yml"

    with pytest.raises(TypeError):
        _Unbound.get_instance()


def test_singleton_returns_same_instance(tmp_path, monkeypatch):
    yaml_path = tmp_path / "dev.yml"
    _ExtendedSettings(JOBS_DIR="/x").save_yaml_settings(str(yaml_path))

    class _SingletonA(BaseAppSettingsSingleton):
        _settings_class = _ExtendedSettings
        _dev_yaml = str(yaml_path)
        _prod_yaml = str(yaml_path)

    monkeypatch.delenv("APP_ENV", raising=False)
    first = _SingletonA.get_instance()
    second = _SingletonA.get_instance()
    assert first is second
    assert first.JOBS_DIR == "/x"


def test_singleton_prod_env_picks_prod_yaml(tmp_path, monkeypatch):
    dev_yaml = tmp_path / "dev.yml"
    prod_yaml = tmp_path / "prod.yml"
    _ExtendedSettings(JOBS_DIR="DEV").save_yaml_settings(str(dev_yaml))
    _ExtendedSettings(JOBS_DIR="PROD").save_yaml_settings(str(prod_yaml))

    class _SingletonB(BaseAppSettingsSingleton):
        _settings_class = _ExtendedSettings
        _dev_yaml = str(dev_yaml)
        _prod_yaml = str(prod_yaml)

    monkeypatch.setenv("APP_ENV", "production")
    instance = _SingletonB.get_instance()
    assert instance.JOBS_DIR == "PROD"


def test_singleton_update_from_yaml_replaces_instance(tmp_path, monkeypatch):
    yaml_path = tmp_path / "dev.yml"
    _ExtendedSettings(JOBS_DIR="one").save_yaml_settings(str(yaml_path))

    class _SingletonC(BaseAppSettingsSingleton):
        _settings_class = _ExtendedSettings
        _dev_yaml = str(yaml_path)
        _prod_yaml = str(yaml_path)

    monkeypatch.delenv("APP_ENV", raising=False)
    first = _SingletonC.get_instance()
    assert first.JOBS_DIR == "one"

    new_yaml = "JOBS_DIR: two\nCUSTOM_FLAG: true\n"
    updated = _SingletonC.update_settings_from_yaml(new_yaml)
    assert updated is not first
    assert updated.JOBS_DIR == "two"
    assert _SingletonC.get_instance() is updated
