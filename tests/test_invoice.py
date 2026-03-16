"""Tests for timecard.invoice — PDF generation with mocked WeasyPrint."""

from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch

import pytest

from timecard.config import Settings
from timecard.db import add_entry, get_connection, get_entries
from timecard.invoice import _get_period_dates, _render_invoice_html, generate_invoice
from timecard.models import Entry


@pytest.fixture
def conn(tmp_path):
    return get_connection(tmp_path / "test.db")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        hourly_rate=150.0,
        contractor_name="Jane Smith",
        contractor_address="456 Elm St",
        contractor_email="jane@example.com",
        client_name="Acme Corp",
        client_address="123 Main St",
        invoice_output_dir=str(tmp_path / "invoices"),
        payment_instructions="Pay within 30 days.",
    )


class TestGetPeriodDates:
    def test_week_is_7_days(self):
        start, end = _get_period_dates("week")
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        assert (e - s).days == 6
        # start should be a Monday, end should be a Sunday
        assert s.isoweekday() == 1  # Monday
        assert e.isoweekday() == 7  # Sunday

    def test_biweekly_is_14_days(self):
        start, end = _get_period_dates("biweekly")
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        assert (e - s).days == 13
        assert s.isoweekday() == 1  # Monday
        assert e.isoweekday() == 7  # Sunday

    def test_month_is_complete_previous_month(self):
        start, end = _get_period_dates("month")
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        # Start should be 1st of a month
        assert s.day == 1
        # End should be last day of that same month
        next_day = e + timedelta(days=1)
        assert next_day.day == 1
        # Start and end should be in the same month
        assert s.month == e.month

    def test_week_ends_before_today(self):
        start, end = _get_period_dates("week")
        today = datetime.now(timezone.utc).date()
        assert date.fromisoformat(end) < today


class TestRenderInvoiceHtml:
    def test_renders_html_with_data(self, settings):
        entries = [
            Entry(
                id=1,
                started_at="2025-01-15T09:00:00",
                ended_at="2025-01-15T12:00:00",
                duration_minutes=180,
                note="API work",
            )
        ]
        html = _render_invoice_html(
            entries=entries,
            invoice_number="INV-0001",
            period_start="2025-01-01",
            period_end="2025-01-15",
            total_hours=3.0,
            total_amount=450.0,
            hourly_rate=150.0,
            settings=settings,
            note="Q1 work",
        )
        assert "INV-0001" in html
        assert "Jane Smith" in html
        assert "Acme Corp" in html
        assert "API work" in html
        assert "$450.00" in html
        assert "Q1 work" in html

    def test_renders_without_note(self, settings):
        entries = [
            Entry(id=1, started_at="2025-01-15T09:00:00", duration_minutes=60)
        ]
        html = _render_invoice_html(
            entries=entries,
            invoice_number="INV-0001",
            period_start="2025-01-01",
            period_end="2025-01-15",
            total_hours=1.0,
            total_amount=150.0,
            hourly_rate=150.0,
            settings=settings,
        )
        assert "INV-0001" in html


class TestGenerateInvoice:
    @patch("timecard.invoice._write_pdf")
    def test_generate_all_uninvoiced(self, mock_pdf, conn, settings, tmp_path):
        """No period → invoices all uninvoiced entries."""
        add_entry(
            conn,
            Entry(started_at="2025-01-10T09:00:00", duration_minutes=180, note="Work A"),
        )
        add_entry(
            conn,
            Entry(started_at="2025-02-20T09:00:00", duration_minutes=120, note="Work B"),
        )

        output_path = str(tmp_path / "test-invoice.pdf")
        invoice = generate_invoice(conn, settings, output_path=output_path, note="All work")

        assert invoice.id is not None
        assert invoice.invoice_number == "INV-0001"
        assert invoice.total_hours == 5.0
        assert invoice.total_amount == 750.0
        assert invoice.period_start == "2025-01-10"
        assert invoice.period_end == "2025-02-20"
        mock_pdf.assert_called_once()

        # Verify entries are marked as invoiced
        entries = get_entries(conn, invoiced=True)
        assert len(entries) == 2
        assert all(e.invoice_id == invoice.id for e in entries)

    @patch("timecard.invoice._write_pdf")
    def test_generate_with_period_filter(self, mock_pdf, conn, settings, tmp_path):
        """Period filter only includes entries in that window."""
        # Get last complete Mon-Sun week
        today = datetime.now(timezone.utc).date()
        days_since_sunday = today.isoweekday() % 7
        last_sunday = today - timedelta(days=days_since_sunday)
        last_monday = last_sunday - timedelta(days=6)

        add_entry(
            conn,
            Entry(started_at=f"{last_monday}T09:00:00", duration_minutes=60),
        )
        # Entry outside the week window — should not be included
        add_entry(
            conn,
            Entry(started_at="2024-01-01T09:00:00", duration_minutes=60),
        )

        invoice = generate_invoice(
            conn, settings, period="week", output_path=str(tmp_path / "inv.pdf")
        )
        assert invoice.total_hours == 1.0

        # Old entry should still be uninvoiced
        uninvoiced = get_entries(conn, invoiced=False)
        assert len(uninvoiced) == 1
        assert uninvoiced[0].started_at.startswith("2024-01-01")

    @patch("timecard.invoice._write_pdf")
    def test_no_entries_raises(self, mock_pdf, conn, settings):
        with pytest.raises(ValueError, match="No uninvoiced entries"):
            generate_invoice(conn, settings)

    @patch("timecard.invoice._write_pdf")
    def test_no_entries_with_period_raises(self, mock_pdf, conn, settings):
        with pytest.raises(ValueError, match="No uninvoiced entries found for period"):
            generate_invoice(conn, settings, period="week")

    @patch("timecard.invoice._write_pdf")
    def test_auto_path(self, mock_pdf, conn, settings):
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        invoice = generate_invoice(conn, settings)
        assert "INV-0001" in invoice.pdf_path

    @patch("timecard.invoice._write_pdf")
    def test_invoice_number_increments(self, mock_pdf, conn, settings):
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        inv1 = generate_invoice(conn, settings)
        assert inv1.invoice_number == "INV-0001"

        add_entry(conn, Entry(started_at="2025-01-16T14:00:00", duration_minutes=60))
        inv2 = generate_invoice(conn, settings)
        assert inv2.invoice_number == "INV-0002"

    @patch("timecard.invoice._write_pdf")
    def test_invoice_number_start_offset(self, mock_pdf, conn, settings, tmp_path):
        """INVOICE_NUMBER_START offsets the auto-incremented number."""
        settings_with_offset = Settings(
            hourly_rate=150.0,
            contractor_name="Jane Smith",
            contractor_address="456 Elm St",
            contractor_email="jane@example.com",
            client_name="Acme Corp",
            client_address="123 Main St",
            invoice_output_dir=str(tmp_path / "invoices"),
            payment_instructions="Pay within 30 days.",
            invoice_number_start=100,
        )
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        inv1 = generate_invoice(conn, settings_with_offset)
        assert inv1.invoice_number == "INV-0101"

        add_entry(conn, Entry(started_at="2025-01-16T09:00:00", duration_minutes=60))
        inv2 = generate_invoice(conn, settings_with_offset)
        assert inv2.invoice_number == "INV-0102"

    @patch("timecard.invoice._write_pdf")
    def test_number_override(self, mock_pdf, conn, settings):
        """--number overrides the auto-incremented invoice number."""
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        inv = generate_invoice(conn, settings, number=42)
        assert inv.invoice_number == "INV-0042"

    @patch("timecard.invoice._write_pdf")
    def test_number_override_does_not_affect_next_auto(self, mock_pdf, conn, settings):
        """A manual number override doesn't shift subsequent auto-numbers."""
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        generate_invoice(conn, settings, number=99)

        add_entry(conn, Entry(started_at="2025-01-16T09:00:00", duration_minutes=60))
        inv2 = generate_invoice(conn, settings)
        # The DB has 1 invoice row now, so next auto number is INV-0002
        assert inv2.invoice_number == "INV-0002"

    @patch("timecard.invoice._write_pdf")
    def test_number_override_duplicate_raises(self, mock_pdf, conn, settings):
        """Reusing an existing invoice number raises ValueError."""
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        generate_invoice(conn, settings, number=42)

        add_entry(conn, Entry(started_at="2025-01-16T09:00:00", duration_minutes=60))
        with pytest.raises(ValueError, match="INV-0042 already exists"):
            generate_invoice(conn, settings, number=42)

    @patch("timecard.invoice._write_pdf")
    def test_number_override_negative_raises(self, mock_pdf, conn, settings):
        """A negative invoice number raises ValueError."""
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        with pytest.raises(ValueError, match="must be >= 0"):
            generate_invoice(conn, settings, number=-1)

    def test_start_offset_negative_raises(self, conn):
        """A negative start_offset in get_next_invoice_number raises ValueError."""
        from timecard.db import get_next_invoice_number
        with pytest.raises(ValueError, match="start_offset must be >= 0"):
            get_next_invoice_number(conn, start_offset=-1)
