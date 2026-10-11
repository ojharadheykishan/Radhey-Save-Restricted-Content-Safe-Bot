import os
import subprocess
import sys
from pathlib import Path

import pytest

import config


def test_telegram_credentials_load_from_environment():
    project_dir = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        API_ID="123456",
        API_HASH="test-api-hash",
        BOT_TOKEN="123456:test-bot-token",
    )
    check = (
        "import config; "
        "assert config.API_ID == 123456; "
        "assert config.API_HASH == 'test-api-hash'; "
        "assert config.BOT_TOKEN == '123456:test-bot-token'"
    )

    subprocess.run(
        [sys.executable, "-c", check],
        cwd=project_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


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
