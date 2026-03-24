"""Tests for timecard.config."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from timecard.config import Settings, load_settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.hourly_rate == 150.0
        assert s.contractor_name == ""
        assert s.time_format == "24h"

    def test_get_db_path(self, tmp_path):
        s = Settings(db_path=str(tmp_path / "data" / "test.db"))
        db_path = s.get_db_path()
        assert db_path == tmp_path / "data" / "test.db"
        assert db_path.parent.exists()

    def test_get_db_path_raises_if_directory(self, tmp_path):
        s = Settings(db_path=str(tmp_path))
        with pytest.raises(ValueError, match="resolves to a directory"):
            s.get_db_path()

    def test_get_invoice_output_dir(self, tmp_path):
        s = Settings(invoice_output_dir=str(tmp_path / "invoices"))
        out = s.get_invoice_output_dir()
        assert out.exists()
        assert out == tmp_path / "invoices"


class TestLoadSettings:
    def test_load_from_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            'HOURLY_RATE=200\nCONTRACTOR_NAME="Test User"\n'
        )
        # Clear any existing env vars that might interfere
        for key in ["HOURLY_RATE", "CONTRACTOR_NAME"]:
            os.environ.pop(key, None)

        settings = load_settings(str(env_file))
        assert settings.hourly_rate == 200.0
        assert settings.contractor_name == "Test User"

        # Clean up env vars set by dotenv
        for key in ["HOURLY_RATE", "CONTRACTOR_NAME"]:
            os.environ.pop(key, None)

    def test_env_var_override(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("HOURLY_RATE=100\n")
        monkeypatch.setenv("HOURLY_RATE", "250")
        settings = load_settings(str(env_file))
        assert settings.hourly_rate == 250.0
        monkeypatch.delenv("HOURLY_RATE", raising=False)

    def test_db_path_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TIMECARD_DB_PATH", str(tmp_path / "custom.db"))
        settings = load_settings(str(tmp_path / "nonexistent.env"))
        assert settings.db_path == str(tmp_path / "custom.db")
        monkeypatch.delenv("TIMECARD_DB_PATH", raising=False)

    def test_empty_env_var_wins_over_file_value(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("CONTRACTOR_NAME=FileValue\n")
        monkeypatch.setenv("CONTRACTOR_NAME", "")
        settings = load_settings(str(env_file))
        assert settings.contractor_name == ""
        monkeypatch.delenv("CONTRACTOR_NAME", raising=False)

    def test_time_format_loaded_from_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TIME_FORMAT=24h\n")
        os.environ.pop("TIME_FORMAT", None)
        settings = load_settings(str(env_file))
        assert settings.time_format == "24h"

    def test_time_format_env_var_override(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("TIME_FORMAT=12h\n")
        monkeypatch.setenv("TIME_FORMAT", "24h")
        settings = load_settings(str(env_file))
        assert settings.time_format == "24h"

    def test_time_format_defaults_to_24h(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        os.environ.pop("TIME_FORMAT", None)
        settings = load_settings(str(env_file))
        assert settings.time_format == "24h"

    def test_xdg_config_home_respected(self, tmp_path, monkeypatch):
        xdg_config = tmp_path / "xdg_config"
        config_dir = xdg_config / "timecard"
        config_dir.mkdir(parents=True)
        (config_dir / ".env").write_text("HOURLY_RATE=99\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
        monkeypatch.delenv("TIMECARD_CONFIG_PATH", raising=False)
        monkeypatch.delenv("HOURLY_RATE", raising=False)

        # Re-import to pick up updated DEFAULT_CONFIG_PATH
        import importlib
        import timecard.config as cfg_module
        importlib.reload(cfg_module)
        from timecard.config import load_settings as _load

        settings = _load()
        assert settings.hourly_rate == 99.0

        importlib.reload(cfg_module)  # restore for other tests
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
