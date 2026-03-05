"""Tests for timecard.cli — Typer CLI commands via CliRunner."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from timecard.cli import app
from timecard.config import Settings
from timecard.db import add_entry, get_connection, get_entry
from timecard.models import Entry

runner = CliRunner()


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Set up a temp database and config for all CLI tests."""
    db_path = tmp_path / "test.db"
    env_file = tmp_path / ".env"
    env_file.write_text(f'HOURLY_RATE=100\nINVOICE_OUTPUT_DIR={tmp_path / "invoices"}\n')
    monkeypatch.setenv("TIMECARD_DB_PATH", str(db_path))
    monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(env_file))
    return db_path


class TestStartStop:
    def test_start(self, tmp_db):
        result = runner.invoke(app, ["start", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "started"

    def test_start_twice_errors(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["start", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_stop(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["stop", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "stopped"
        assert "entry_id" in data

    def test_stop_without_start_errors(self, tmp_db):
        result = runner.invoke(app, ["stop", "--json"])
        assert result.exit_code == 1

    def test_status_no_timer(self, tmp_db):
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["running"] is False

    def test_status_running(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["running"] is True


class TestAdd:
    def test_add_entry(self, tmp_db):
        result = runner.invoke(
            app, ["add", "--date", "2025-01-15", "--hours", "3.5", "--note", "Test work", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "added"
        assert data["hours"] == 3.5

    def test_add_without_note(self, tmp_db):
        result = runner.invoke(
            app, ["add", "--date", "2025-01-15", "--hours", "2", "--json"]
        )
        assert result.exit_code == 0


class TestLog:
    def test_log_empty(self, tmp_db):
        result = runner.invoke(app, ["log"])
        assert result.exit_code == 0
        assert "No entries" in result.stdout

    def test_log_with_entries(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "3.5", "--note", "Work"])
        result = runner.invoke(app, ["log", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["hours"] == 3.5

    def test_log_table_format(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "2", "--note", "Coding"])
        result = runner.invoke(app, ["log"])
        assert result.exit_code == 0
        assert "2025-01-15" in result.stdout
        assert "Coding" in result.stdout


class TestEdit:
    def test_edit_hours(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "1", "--json"])
        result = runner.invoke(app, ["edit", "1", "--hours", "2.5", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "updated"

    def test_edit_note(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "1"])
        result = runner.invoke(app, ["edit", "1", "--note", "Updated", "--json"])
        assert result.exit_code == 0

    def test_edit_no_fields_errors(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "1"])
        result = runner.invoke(app, ["edit", "1", "--json"])
        assert result.exit_code == 1

    def test_edit_nonexistent_errors(self, tmp_db):
        result = runner.invoke(app, ["edit", "999", "--hours", "1", "--json"])
        assert result.exit_code == 1


class TestDelete:
    def test_delete_with_confirm(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "1"])
        result = runner.invoke(app, ["delete", "1", "--yes", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "deleted"

    def test_delete_nonexistent_errors(self, tmp_db):
        result = runner.invoke(app, ["delete", "999", "--yes", "--json"])
        assert result.exit_code == 1

    def test_delete_cancelled(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "1"])
        result = runner.invoke(app, ["delete", "1"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.stdout


class TestInvoice:
    @patch("timecard.invoice._write_pdf")
    def test_generate_invoice(self, mock_pdf, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "3", "--note", "Work"])
        result = runner.invoke(app, ["invoice", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "generated"
        assert data["total_hours"] == 3.0
        assert data["total_amount"] == 300.0  # 3h * $100/hr

    @patch("timecard.invoice._write_pdf")
    def test_invoice_no_entries_errors(self, mock_pdf, tmp_db):
        result = runner.invoke(app, ["invoice", "--json"])
        assert result.exit_code == 1


class TestSync:
    def test_sync_no_sheet_id_errors(self, tmp_db):
        result = runner.invoke(app, ["sync", "--json"])
        assert result.exit_code == 2
        data = json.loads(result.stdout)
        assert "error" in data


class TestAuth:
    @patch("timecard.sync.authenticate", side_effect=FileNotFoundError("No secrets"))
    def test_auth_no_secrets_errors(self, mock_auth, tmp_db):
        result = runner.invoke(app, ["auth", "--json"])
        assert result.exit_code == 2
