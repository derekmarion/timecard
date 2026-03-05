"""Tests for timecard.mcp_server — MCP tool unit tests."""

from unittest.mock import patch

import pytest

from timecard.db import add_entry, get_connection
from timecard.models import Entry


@pytest.fixture
def mock_conn(tmp_path, monkeypatch):
    """Set up a temp database for MCP tool tests."""
    db_path = tmp_path / "test.db"
    env_file = tmp_path / ".env"
    env_file.write_text(f'HOURLY_RATE=100\nINVOICE_OUTPUT_DIR={tmp_path / "invoices"}\n')
    monkeypatch.setenv("TIMECARD_DB_PATH", str(db_path))
    monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(env_file))
    return db_path


class TestStartTimer:
    def test_returns_expected_structure(self, mock_conn):
        from timecard.mcp_server import start_timer

        result = start_timer()
        assert result["status"] == "started"
        assert "started_at" in result


class TestStopTimer:
    def test_returns_expected_structure(self, mock_conn):
        from timecard.mcp_server import start_timer, stop_timer

        start_timer()
        result = stop_timer()
        assert result["status"] == "stopped"
        assert "entry_id" in result
        assert "hours" in result

    def test_stop_without_start_raises(self, mock_conn):
        from timecard.mcp_server import stop_timer

        with pytest.raises(ValueError):
            stop_timer()


class TestGetStatus:
    def test_no_timer(self, mock_conn):
        from timecard.mcp_server import get_status

        result = get_status()
        assert result["running"] is False

    def test_timer_running(self, mock_conn):
        from timecard.mcp_server import get_status, start_timer

        start_timer()
        result = get_status()
        assert result["running"] is True
        assert "elapsed_minutes" in result


class TestAddEntry:
    def test_returns_expected_structure(self, mock_conn):
        from timecard.mcp_server import add_entry_tool

        result = add_entry_tool(date="2025-01-15", hours=3.5, note="Test")
        assert result["status"] == "added"
        assert "entry_id" in result


class TestGetLog:
    def test_returns_list(self, mock_conn):
        from timecard.mcp_server import add_entry_tool, get_log

        add_entry_tool(date="2025-01-15", hours=2.0)
        result = get_log()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["hours"] == 2.0

    def test_empty_log(self, mock_conn):
        from timecard.mcp_server import get_log

        result = get_log()
        assert result == []


class TestEditEntry:
    def test_edit_success(self, mock_conn):
        from timecard.mcp_server import add_entry_tool, edit_entry

        add_entry_tool(date="2025-01-15", hours=1.0)
        result = edit_entry(id=1, hours=2.5)
        assert result["status"] == "updated"

    def test_edit_not_found(self, mock_conn):
        from timecard.mcp_server import edit_entry

        result = edit_entry(id=999, hours=1.0)
        assert "error" in result


class TestDeleteEntry:
    def test_delete_success(self, mock_conn):
        from timecard.mcp_server import add_entry_tool, delete_entry_tool

        add_entry_tool(date="2025-01-15", hours=1.0)
        result = delete_entry_tool(id=1)
        assert result["status"] == "deleted"

    def test_delete_not_found(self, mock_conn):
        from timecard.mcp_server import delete_entry_tool

        result = delete_entry_tool(id=999)
        assert "error" in result


class TestExportCsv:
    def test_returns_csv_string(self, mock_conn):
        from timecard.mcp_server import add_entry_tool, export_csv

        add_entry_tool(date="2025-01-15", hours=2.0, note="Test work")
        result = export_csv()
        assert "ID,Date,Hours,Note,Invoiced" in result
        assert "2025-01-15" in result
        assert "2.0" in result
        assert "Test work" in result

    def test_empty_db(self, mock_conn):
        from timecard.mcp_server import export_csv

        result = export_csv()
        assert "ID,Date,Hours,Note,Invoiced" in result
        lines = result.strip().split("\n")
        assert len(lines) == 1  # header only


class TestGenerateInvoice:
    @patch("timecard.invoice._write_pdf")
    def test_returns_expected_structure(self, mock_pdf, mock_conn):
        from timecard.mcp_server import add_entry_tool
        from timecard.mcp_server import generate_invoice

        add_entry_tool(date="2025-01-15", hours=3.0, note="Work")
        result = generate_invoice()
        assert result["status"] == "generated"
        assert result["total_hours"] == 3.0
        assert result["total_amount"] == 300.0
        assert "pdf_path" in result


class TestSyncToSheets:
    def test_no_sheet_id_raises(self, mock_conn):
        from timecard.mcp_server import sync_to_sheets

        with pytest.raises(ValueError, match="Google Sheet ID not configured"):
            sync_to_sheets()
