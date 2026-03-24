"""Tests for timecard.cli — Typer CLI commands via CliRunner."""

import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from timecard.cli import _format_ts, app
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


class TestPauseResume:
    def test_pause(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["pause", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "paused"

    def test_pause_without_timer_errors(self, tmp_db):
        result = runner.invoke(app, ["pause", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_pause_already_paused_errors(self, tmp_db):
        runner.invoke(app, ["start"])
        runner.invoke(app, ["pause"])
        result = runner.invoke(app, ["pause", "--json"])
        assert result.exit_code == 1

    def test_resume(self, tmp_db):
        runner.invoke(app, ["start"])
        runner.invoke(app, ["pause"])
        result = runner.invoke(app, ["resume", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "resumed"

    def test_resume_without_pause_errors(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["resume", "--json"])
        assert result.exit_code == 1

    def test_stop_while_paused(self, tmp_db):
        runner.invoke(app, ["start"])
        runner.invoke(app, ["pause"])
        result = runner.invoke(app, ["stop", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "stopped"

    def test_status_shows_paused(self, tmp_db):
        runner.invoke(app, ["start"])
        runner.invoke(app, ["pause"])
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["paused"] is True


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


class TestExport:
    def test_export_stdout(self, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "3.5", "--note", "Work"])
        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        assert "ID,Date,Hours,Note,Invoiced" in result.stdout
        assert "2025-01-15" in result.stdout
        assert "3.5" in result.stdout
        assert "Work" in result.stdout

    def test_export_to_file(self, tmp_db, tmp_path):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "2", "--note", "Coding"])
        out_file = str(tmp_path / "export.csv")
        result = runner.invoke(app, ["export", "--output", out_file])
        assert result.exit_code == 0
        assert "Exported entries to" in result.stdout
        content = open(out_file).read()
        assert "2025-01-15" in content

    def test_export_empty(self, tmp_db):
        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        assert "ID,Date,Hours,Note,Invoiced" in result.stdout


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

    @patch("timecard.invoice._write_pdf")
    def test_invoice_number_override(self, mock_pdf, tmp_db):
        runner.invoke(app, ["add", "--date", "2025-01-15", "--hours", "2", "--note", "Work"])
        result = runner.invoke(app, ["invoice", "--number", "42", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["invoice_number"] == "INV-0042"


class TestSetup:
    def test_setup_creates_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".config" / "timecard" / ".env"
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        inputs = "\n".join([
            "Jane Smith",
            "456 Elm St",
            "jane@example.com",
            "Acme Corp",
            "123 Main St",
            "150",
            "~/invoices",
            "Please pay within 30 days.",
            "0",
            "12h",  # time format
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        assert config_path.exists()
        content = config_path.read_text()
        assert 'CONTRACTOR_NAME="Jane Smith"' in content
        assert 'CLIENT_NAME="Acme Corp"' in content
        assert "HOURLY_RATE=150" in content
        assert "INVOICE_NUMBER_START=0" in content

    def test_setup_aborts_if_exists_and_no_overwrite(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        config_path.write_text("HOURLY_RATE=100\n")
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        result = runner.invoke(app, ["setup"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.stdout.lower()
        assert config_path.read_text() == "HOURLY_RATE=100\n"

    def test_setup_edit_preserves_existing_values(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        config_path.write_text(
            'CONTRACTOR_NAME="Jane Smith"\nHOURLY_RATE=100\n'
            'CLIENT_NAME="Acme"\nCONTRACTOR_ADDRESS=""\n'
            'CONTRACTOR_EMAIL=""\nCLIENT_ADDRESS=""\n'
            'INVOICE_OUTPUT_DIR=~/invoices\n'
            'PAYMENT_INSTRUCTIONS="Pay me."\n'
        )
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        # Accept all defaults by pressing Enter, except hourly rate
        inputs = "\n".join([
            "y",    # confirm edit
            "",     # contractor name (keep "Jane Smith")
            "",     # contractor address
            "",     # contractor email
            "",     # client name (keep "Acme")
            "",     # client address
            "200",  # update hourly rate
            "",     # invoice output dir
            "",     # payment instructions
            "",     # invoice number offset
            "",     # time format (keep default)
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        content = config_path.read_text()
        assert 'CONTRACTOR_NAME="Jane Smith"' in content
        assert 'CLIENT_NAME="Acme"' in content
        assert "HOURLY_RATE=200" in content

    def test_setup_rejects_negative_invoice_number_offset(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        inputs = "\n".join([
            "", "", "", "", "", "150", "~/invoices", "Pay.",
            "-1",  # rejected
            "5",   # accepted
            "",    # time format (keep default)
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        content = config_path.read_text()
        assert "INVOICE_NUMBER_START=5" in content
        assert "must be 0 or greater" in result.stdout

    def test_setup_handles_invalid_invoice_offset_in_file(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        config_path.write_text("INVOICE_NUMBER_START=\n")
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        inputs = "\n".join([
            "y",   # confirm edit
            "", "", "", "", "", "150", "~/invoices", "Pay.", "", "",
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        assert "INVOICE_NUMBER_START=0" in config_path.read_text()

    def test_setup_escapes_quotes_in_values(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        inputs = "\n".join([
            'O\'Brien & "Co"',  # name with embedded double quotes
            "", "", "", "", "100", "~/invoices", "Pay.", "0", "",
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        content = config_path.read_text()
        assert '\\"' in content  # double quotes are escaped

    def test_setup_writes_time_format(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        inputs = "\n".join([
            "", "", "", "", "", "150", "~/invoices", "Pay.", "0", "", "24h",
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        assert "TIME_FORMAT=24h" in config_path.read_text()

    def test_setup_rejects_invalid_time_format(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        inputs = "\n".join([
            "", "", "", "", "", "150", "~/invoices", "Pay.", "0",
            "bad",  # rejected
            "12h",  # accepted
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        assert "TIME_FORMAT=12h" in config_path.read_text()
        assert "must be '12h' or '24h'" in result.stdout

    def test_setup_preserves_existing_time_format(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".env"
        config_path.write_text("TIME_FORMAT=24h\nHOURLY_RATE=100\n")
        monkeypatch.setenv("TIMECARD_CONFIG_PATH", str(config_path))

        # Accept all defaults — time format should default to "24h" from file
        inputs = "\n".join([
            "y",   # confirm edit
            "", "", "", "", "", "", "", "", "", "", "",
        ])
        result = runner.invoke(app, ["setup"], input=inputs + "\n")
        assert result.exit_code == 0
        assert "TIME_FORMAT=24h" in config_path.read_text()


class TestUpdate:
    def _make_proc(self, returncode=0, stderr="", stdout=""):
        m = MagicMock()
        m.returncode = returncode
        m.stderr = stderr
        m.stdout = stdout
        return m

    @patch("subprocess.run")
    def test_update_success(self, mock_run):
        mock_run.return_value = self._make_proc(returncode=0)
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 0
        assert "status: updated" in result.stdout

    @patch("subprocess.run")
    def test_update_success_json(self, mock_run):
        mock_run.return_value = self._make_proc(returncode=0)
        result = runner.invoke(app, ["update", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "updated"

    @patch("subprocess.run")
    def test_update_cache_clear_fails(self, mock_run):
        mock_run.return_value = self._make_proc(returncode=1, stderr="cache error")
        result = runner.invoke(app, ["update", "--json"])
        assert result.exit_code == 2
        data = json.loads(result.stdout)
        assert "error" in data
        assert "cache error" in data["error"]

    @patch("subprocess.run")
    def test_update_install_fails(self, mock_run):
        def side_effect(cmd, **kwargs):
            if "cache" in cmd:
                return self._make_proc(returncode=0)
            return self._make_proc(returncode=1, stderr="install error")

        mock_run.side_effect = side_effect
        result = runner.invoke(app, ["update", "--json"])
        assert result.exit_code == 2
        data = json.loads(result.stdout)
        assert "error" in data
        assert "install error" in data["error"]

    @patch("subprocess.run")
    def test_update_error_includes_stdout(self, mock_run):
        m = MagicMock()
        m.returncode = 1
        m.stderr = "stderr msg"
        m.stdout = "stdout msg"
        mock_run.return_value = m
        result = runner.invoke(app, ["update", "--json"])
        assert result.exit_code == 2
        data = json.loads(result.stdout)
        assert "stderr msg" in data["error"]
        assert "stdout msg" in data["error"]

    @patch("subprocess.run", side_effect=FileNotFoundError("uv not found"))
    def test_update_uv_not_found(self, mock_run):
        result = runner.invoke(app, ["update", "--json"])
        assert result.exit_code == 2
        data = json.loads(result.stdout)
        assert "error" in data
        assert "uv not found" in data["error"]


class TestTimestampFormatting:
    """Tests for human-readable timestamp formatting in CLI text output."""

    _ISO_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_format_ts_returns_readable_string(self):
        iso = "2026-03-24T15:30:00+00:00"
        result = _format_ts(iso)
        assert not self._ISO_PATTERN.search(result)
        assert "Mar" in result
        assert "2026" in result

    def test_format_ts_preserves_time(self):
        iso = "2026-03-24T15:30:00+00:00"
        result = _format_ts(iso, "12h")
        assert "AM" in result or "PM" in result

    def test_start_text_output_is_formatted(self, tmp_db):
        result = runner.invoke(app, ["start"])
        assert result.exit_code == 0
        assert not self._ISO_PATTERN.search(result.stdout)

    def test_start_json_output_preserves_iso(self, tmp_db):
        result = runner.invoke(app, ["start", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert self._ISO_PATTERN.search(data["started_at"])

    def test_pause_text_output_is_formatted(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["pause"])
        assert result.exit_code == 0
        assert not self._ISO_PATTERN.search(result.stdout)

    def test_pause_json_output_preserves_iso(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["pause", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert self._ISO_PATTERN.search(data["paused_at"])

    def test_resume_text_output_is_formatted(self, tmp_db):
        runner.invoke(app, ["start"])
        runner.invoke(app, ["pause"])
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 0
        assert not self._ISO_PATTERN.search(result.stdout)

    def test_resume_json_output_preserves_iso(self, tmp_db):
        runner.invoke(app, ["start"])
        runner.invoke(app, ["pause"])
        result = runner.invoke(app, ["resume", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert self._ISO_PATTERN.search(data["resumed_at"])

    def test_status_text_output_is_formatted(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert not self._ISO_PATTERN.search(result.stdout)

    def test_status_json_output_preserves_iso(self, tmp_db):
        runner.invoke(app, ["start"])
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert self._ISO_PATTERN.search(data["started_at"])

    def test_format_ts_12h_contains_am_pm(self):
        iso = "2026-03-24T15:30:00+00:00"
        result = _format_ts(iso, "12h")
        assert "AM" in result or "PM" in result

    def test_format_ts_24h_no_am_pm(self):
        iso = "2026-03-24T15:30:00+00:00"
        result = _format_ts(iso, "24h")
        assert "AM" not in result
        assert "PM" not in result

    def test_start_respects_24h_format(self, tmp_db, monkeypatch):
        monkeypatch.setenv("TIME_FORMAT", "24h")
        result = runner.invoke(app, ["start"])
        assert result.exit_code == 0
        assert "AM" not in result.stdout
        assert "PM" not in result.stdout
        assert not self._ISO_PATTERN.search(result.stdout)

    def test_start_respects_12h_format(self, tmp_db, monkeypatch):
        monkeypatch.setenv("TIME_FORMAT", "12h")
        result = runner.invoke(app, ["start"])
        assert result.exit_code == 0
        assert "AM" in result.stdout or "PM" in result.stdout
