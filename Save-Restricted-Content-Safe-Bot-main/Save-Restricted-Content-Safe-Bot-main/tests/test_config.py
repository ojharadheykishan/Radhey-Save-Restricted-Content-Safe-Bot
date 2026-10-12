import os
import importlib

import pytest

import config


def test_telegram_credentials_load_from_environment(monkeypatch):
    original = (config.API_ID, config.API_HASH, config.BOT_TOKEN)
    monkeypatch.setenv("API_ID", str(original[0]))
    monkeypatch.setenv("API_HASH", "test-api-hash")
    monkeypatch.setenv("BOT_TOKEN", "123456:test-bot-token")

    importlib.reload(config)

    assert config.API_ID == original[0]
    assert config.API_HASH == "test-api-hash"
    assert config.BOT_TOKEN == "123456:test-bot-token"

    config.API_ID, config.API_HASH, config.BOT_TOKEN = original


def test_api_id_loads_from_environment(monkeypatch):
    original = (config.API_ID, config.API_HASH, config.BOT_TOKEN)
    monkeypatch.setenv("API_ID", "123456")
    monkeypatch.setenv("API_HASH", "test-api-hash")
    monkeypatch.setenv("BOT_TOKEN", "123456:test-bot-token")

    importlib.reload(config)

    assert config.API_ID == 123456

    config.API_ID, config.API_HASH, config.BOT_TOKEN = original


def test_required_config_reports_missing_telegram_credentials(monkeypatch):
    monkeypatch.setattr(config, "API_ID", 0)
    monkeypatch.setattr(config, "API_HASH", "")
    monkeypatch.setattr(config, "BOT_TOKEN", "")

    with pytest.raises(RuntimeError, match="API_ID, API_HASH, BOT_TOKEN"):
        config.validate_required_config()


def test_required_config_accepts_telegram_credentials(monkeypatch):
    monkeypatch.setattr(config, "API_ID", 123456)
    monkeypatch.setattr(config, "API_HASH", "test-api-hash")
    monkeypatch.setattr(config, "BOT_TOKEN", "123456:test-bot-token")

    config.validate_required_config()
