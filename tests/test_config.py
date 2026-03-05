"""Tests for timecard.config."""

import os
from pathlib import Path

from timecard.config import Settings, load_settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.hourly_rate == 150.0
        assert s.contractor_name == ""

    def test_get_db_path(self, tmp_path):
        s = Settings(db_path=str(tmp_path / "data" / "test.db"))
        db_path = s.get_db_path()
        assert db_path == tmp_path / "data" / "test.db"
        assert db_path.parent.exists()

    def test_get_invoice_output_dir(self, tmp_path):
        s = Settings(invoice_output_dir=str(tmp_path / "invoices"))
        out = s.get_invoice_output_dir()
        assert out.exists()
        assert out == tmp_path / "invoices"


class TestLoadSettings:
    def test_load_from_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            'HOURLY_RATE=200\nCONTRACTOR_NAME="Test User"\nGOOGLE_SHEET_ID=abc123\n'
        )
        # Clear any existing env vars that might interfere
        for key in ["HOURLY_RATE", "CONTRACTOR_NAME", "GOOGLE_SHEET_ID"]:
            os.environ.pop(key, None)

        settings = load_settings(str(env_file))
        assert settings.hourly_rate == 200.0
        assert settings.contractor_name == "Test User"
        assert settings.google_sheet_id == "abc123"

        # Clean up env vars set by dotenv
        for key in ["HOURLY_RATE", "CONTRACTOR_NAME", "GOOGLE_SHEET_ID"]:
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

    def test_empty_google_sheet_id_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "")
        settings = load_settings(str(tmp_path / "nonexistent.env"))
        assert settings.google_sheet_id is None
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
