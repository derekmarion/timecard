"""Tests for timecard.models."""

from datetime import datetime, timedelta, timezone

from timecard.models import ActiveSession, Entry, Invoice


class TestEntry:
    def test_default_values(self):
        entry = Entry()
        assert entry.id is None
        assert entry.invoiced is False
        assert entry.hours() == 0.0

    def test_hours_calculation(self):
        entry = Entry(duration_minutes=90)
        assert entry.hours() == 1.5

    def test_hours_zero_duration(self):
        entry = Entry(duration_minutes=0)
        assert entry.hours() == 0.0

    def test_hours_rounding(self):
        entry = Entry(duration_minutes=100)
        assert entry.hours() == 1.67

    def test_full_entry(self):
        entry = Entry(
            id=1,
            started_at="2025-01-15T09:00:00",
            ended_at="2025-01-15T12:30:00",
            duration_minutes=210,
            note="API work",
            invoiced=True,
            invoice_id=5,
        )
        assert entry.hours() == 3.5
        assert entry.note == "API work"


class TestInvoice:
    def test_default_values(self):
        inv = Invoice()
        assert inv.id is None
        assert inv.invoice_number is None

    def test_full_invoice(self):
        inv = Invoice(
            id=1,
            invoice_number="INV-0001",
            period_start="2025-01-01",
            period_end="2025-01-15",
            total_hours=40.0,
            total_amount=6000.0,
            created_at="2025-01-16T00:00:00",
            pdf_path="/tmp/inv.pdf",
            note="Backend dev",
        )
        assert inv.total_amount == 6000.0


class TestActiveSession:
    def test_default_values(self):
        session = ActiveSession()
        assert session.id == 1
        assert session.started_at is None
        assert session.elapsed_minutes() == 0.0

    def test_elapsed_minutes(self):
        now = datetime.now(timezone.utc)
        ten_min_ago = (now - timedelta(minutes=10)).isoformat()
        session = ActiveSession(started_at=ten_min_ago)
        elapsed = session.elapsed_minutes()
        assert 9.5 < elapsed < 10.5
