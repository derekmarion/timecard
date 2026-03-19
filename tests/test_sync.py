"""Tests for timecard.sync — Google Sheets integration with mocked API calls."""

import importlib
from unittest.mock import MagicMock, patch

import pytest

from timecard.config import Settings
from timecard.db import add_entry, get_connection
from timecard.models import Entry
from timecard.sync import sync_to_sheets


@pytest.fixture
def conn(tmp_path):
    return get_connection(tmp_path / "test.db")


@pytest.fixture
def settings():
    return Settings(google_sheet_id="test-sheet-id")


class TestCredentialPaths:
    def test_default_credential_dir(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        import timecard.sync as sync_module
        importlib.reload(sync_module)
        assert str(sync_module.CREDENTIALS_DIR).endswith("/.config/timecard")
        importlib.reload(sync_module)

    def test_xdg_config_home_overrides_credential_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        import timecard.sync as sync_module
        importlib.reload(sync_module)
        assert sync_module.CREDENTIALS_DIR == tmp_path / "timecard"
        assert sync_module.CLIENT_SECRETS_PATH == tmp_path / "timecard" / "client_secrets.json"
        assert sync_module.TOKEN_PATH == tmp_path / "timecard" / "google_token.json"
        importlib.reload(sync_module)

    def test_empty_xdg_config_home_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        import timecard.sync as sync_module
        importlib.reload(sync_module)
        assert str(sync_module.CREDENTIALS_DIR).endswith("/.config/timecard")
        importlib.reload(sync_module)


class TestSyncToSheets:
    def test_no_sheet_id_raises(self, conn):
        settings = Settings(google_sheet_id=None)
        with pytest.raises(ValueError, match="Google Sheet ID not configured"):
            sync_to_sheets(conn, settings)

    @patch("timecard.sync.gspread")
    def test_sync_empty_db(self, mock_gspread, conn, settings):
        mock_creds = MagicMock()
        count = sync_to_sheets(conn, settings, credentials=mock_creds)
        assert count == 0

    @patch("timecard.sync.gspread")
    def test_sync_entries(self, mock_gspread, conn, settings):
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60, note="Work"))
        add_entry(conn, Entry(started_at="2025-01-16T09:00:00", duration_minutes=120))

        mock_creds = MagicMock()
        mock_sheet = MagicMock()
        mock_sheet.row_values.return_value = []
        mock_sheet.col_values.return_value = ["ID"]  # header only, no existing rows
        mock_gspread.authorize.return_value.open_by_key.return_value.sheet1 = mock_sheet

        count = sync_to_sheets(conn, settings, credentials=mock_creds)
        assert count == 2

        # Verify headers were written
        mock_sheet.update.assert_any_call(
            range_name="A1",
            values=[["ID", "Started At", "Ended At", "Duration (min)", "Note", "Invoiced", "Invoice ID"]],
        )
        # Verify entries were appended
        assert mock_sheet.append_row.call_count == 2

    @patch("timecard.sync.gspread")
    def test_sync_upserts_existing(self, mock_gspread, conn, settings):
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))

        mock_creds = MagicMock()
        mock_sheet = MagicMock()
        expected_headers = ["ID", "Started At", "Ended At", "Duration (min)", "Note", "Invoiced", "Invoice ID"]
        mock_sheet.row_values.return_value = expected_headers
        # Entry ID 1 already exists at row 2
        mock_sheet.col_values.return_value = ["ID", "1"]
        mock_gspread.authorize.return_value.open_by_key.return_value.sheet1 = mock_sheet

        count = sync_to_sheets(conn, settings, credentials=mock_creds)
        assert count == 1

        # Should update row 2, not append
        mock_sheet.update.assert_any_call(
            range_name="A2",
            values=[[1, "2025-01-15T09:00:00", "", 60, "", 0, ""]],
        )
        mock_sheet.append_row.assert_not_called()
