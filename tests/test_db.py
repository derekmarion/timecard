"""Tests for timecard.db."""

import pytest

from timecard.db import (
    add_entry,
    add_invoice,
    delete_entry,
    get_active_session,
    get_connection,
    get_entries,
    get_entry,
    get_invoices,
    get_next_invoice_number,
    mark_entries_invoiced,
    mark_invoice_paid,
    start_session,
    stop_session,
    update_entry,
)
from timecard.models import Entry, Invoice


@pytest.fixture
def conn(tmp_path):
    """Create a fresh DB connection for each test."""
    db_path = tmp_path / "test.db"
    return get_connection(db_path)


class TestSchema:
    def test_tables_created(self, conn):
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "entries" in names
        assert "invoices" in names
        assert "active_session" in names


class TestEntryCRUD:
    def test_add_and_get_entry(self, conn):
        entry = Entry(
            started_at="2025-01-15T09:00:00",
            ended_at="2025-01-15T12:00:00",
            duration_minutes=180,
            note="Test work",
        )
        entry_id = add_entry(conn, entry)
        assert entry_id == 1

        fetched = get_entry(conn, entry_id)
        assert fetched is not None
        assert fetched.duration_minutes == 180
        assert fetched.note == "Test work"
        assert fetched.invoiced is False

    def test_get_nonexistent_entry(self, conn):
        assert get_entry(conn, 999) is None

    def test_get_entries_with_filters(self, conn):
        add_entry(conn, Entry(started_at="2025-01-10T09:00:00", duration_minutes=60))
        add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=120))
        add_entry(conn, Entry(started_at="2025-01-20T09:00:00", duration_minutes=90))

        # All entries
        assert len(get_entries(conn)) == 3

        # Date range
        filtered = get_entries(conn, start_date="2025-01-12", end_date="2025-01-18")
        assert len(filtered) == 1
        assert filtered[0].duration_minutes == 120

        # Uninvoiced only
        uninvoiced = get_entries(conn, invoiced=False)
        assert len(uninvoiced) == 3

    def test_update_entry_hours(self, conn):
        entry_id = add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        assert update_entry(conn, entry_id, hours=2.0)
        updated = get_entry(conn, entry_id)
        assert updated.duration_minutes == 120

    def test_update_entry_note(self, conn):
        entry_id = add_entry(conn, Entry(started_at="2025-01-15T09:00:00", note="old"))
        assert update_entry(conn, entry_id, note="new note")
        assert get_entry(conn, entry_id).note == "new note"

    def test_update_nonexistent_entry(self, conn):
        assert not update_entry(conn, 999, hours=1.0)

    def test_delete_entry(self, conn):
        entry_id = add_entry(conn, Entry(started_at="2025-01-15T09:00:00"))
        assert delete_entry(conn, entry_id)
        assert get_entry(conn, entry_id) is None

    def test_delete_nonexistent_entry(self, conn):
        assert not delete_entry(conn, 999)

    def test_mark_entries_invoiced(self, conn):
        id1 = add_entry(conn, Entry(started_at="2025-01-15T09:00:00", duration_minutes=60))
        id2 = add_entry(conn, Entry(started_at="2025-01-16T09:00:00", duration_minutes=120))
        inv_id = add_invoice(
            conn,
            Invoice(
                invoice_number="INV-0001",
                period_start="2025-01-15",
                period_end="2025-01-16",
                total_hours=3.0,
                total_amount=450.0,
                created_at="2025-01-17T00:00:00",
            ),
        )
        mark_entries_invoiced(conn, [id1, id2], inv_id)
        e1 = get_entry(conn, id1)
        e2 = get_entry(conn, id2)
        assert e1.invoiced is True
        assert e1.invoice_id == inv_id
        assert e2.invoiced is True


class TestInvoice:
    def test_add_invoice(self, conn):
        inv = Invoice(
            invoice_number="INV-0001",
            period_start="2025-01-01",
            period_end="2025-01-15",
            total_hours=40.0,
            total_amount=6000.0,
            created_at="2025-01-16T00:00:00",
            pdf_path="/tmp/inv.pdf",
            note="Q1 work",
        )
        inv_id = add_invoice(conn, inv)
        assert inv_id == 1

    def test_get_next_invoice_number(self, conn):
        assert get_next_invoice_number(conn) == "INV-0001"
        add_invoice(
            conn,
            Invoice(
                invoice_number="INV-0001",
                period_start="2025-01-01",
                period_end="2025-01-15",
                total_hours=1.0,
                total_amount=150.0,
                created_at="2025-01-16T00:00:00",
            ),
        )
        assert get_next_invoice_number(conn) == "INV-0002"


def _make_invoice(n: int) -> Invoice:
    return Invoice(
        invoice_number=f"INV-{n:04d}",
        period_start="2025-01-01",
        period_end="2025-01-15",
        total_hours=1.0,
        total_amount=150.0,
        created_at=f"2025-01-{n:02d}T00:00:00",
    )


class TestInvoiceLifecycle:
    def test_paid_at_column_exists(self, conn):
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(invoices)").fetchall()}
        assert "paid_at" in cols

    def test_get_invoices_empty(self, conn):
        assert get_invoices(conn) == []

    def test_get_invoices_all(self, conn):
        add_invoice(conn, _make_invoice(1))
        add_invoice(conn, _make_invoice(2))
        assert len(get_invoices(conn)) == 2

    def test_get_invoices_paid_filter(self, conn):
        add_invoice(conn, _make_invoice(1))
        add_invoice(conn, _make_invoice(2))
        mark_invoice_paid(conn, "INV-0001")
        paid = get_invoices(conn, paid=True)
        assert len(paid) == 1
        assert paid[0].invoice_number == "INV-0001"

    def test_get_invoices_unpaid_filter(self, conn):
        add_invoice(conn, _make_invoice(1))
        add_invoice(conn, _make_invoice(2))
        mark_invoice_paid(conn, "INV-0001")
        unpaid = get_invoices(conn, paid=False)
        assert len(unpaid) == 1
        assert unpaid[0].invoice_number == "INV-0002"

    def test_mark_invoice_paid_success(self, conn):
        add_invoice(conn, _make_invoice(1))
        result = mark_invoice_paid(conn, "INV-0001")
        assert result is not None
        assert result.invoice_number == "INV-0001"
        assert result.paid_at is not None

    def test_mark_invoice_paid_not_found(self, conn):
        assert mark_invoice_paid(conn, "INV-9999") is None

    def test_mark_invoice_paid_idempotent(self, conn):
        add_invoice(conn, _make_invoice(1))
        first = mark_invoice_paid(conn, "INV-0001")
        second = mark_invoice_paid(conn, "INV-0001")
        assert second is not None
        assert second.paid_at is not None

    def test_paid_at_is_iso8601(self, conn):
        from datetime import datetime

        add_invoice(conn, _make_invoice(1))
        result = mark_invoice_paid(conn, "INV-0001")
        datetime.fromisoformat(result.paid_at)  # raises if invalid


class TestActiveSession:
    def test_no_active_session(self, conn):
        assert get_active_session(conn) is None

    def test_start_session(self, conn):
        start_session(conn, "2025-01-15T09:00:00")
        session = get_active_session(conn)
        assert session is not None
        assert session.started_at == "2025-01-15T09:00:00"

    def test_start_session_already_running(self, conn):
        start_session(conn, "2025-01-15T09:00:00")
        with pytest.raises(ValueError, match="already running"):
            start_session(conn, "2025-01-15T10:00:00")

    def test_stop_session(self, conn):
        start_session(conn, "2025-01-15T09:00:00")
        session = stop_session(conn)
        assert session.started_at == "2025-01-15T09:00:00"
        assert get_active_session(conn) is None

    def test_stop_session_not_running(self, conn):
        with pytest.raises(ValueError, match="No timer session"):
            stop_session(conn)
