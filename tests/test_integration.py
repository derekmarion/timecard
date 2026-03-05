"""End-to-end integration test for TimeCard.

Exercises the complete workflow: start → stop → add → edit → invoice → verify.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from timecard.config import Settings
from timecard.db import get_connection, get_entries, get_entry
from timecard.invoice import generate_invoice
from timecard.timer import start_timer, stop_timer
from timecard.db import add_entry, update_entry
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


@patch("timecard.invoice._write_pdf")
def test_full_workflow(mock_write_pdf, conn, settings, tmp_path):
    """Complete end-to-end workflow as specified in the spec."""
    # Track that _write_pdf actually creates the file so we can verify it exists
    def fake_write_pdf(html_content, output_path):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("fake pdf")

    mock_write_pdf.side_effect = fake_write_pdf

    # 1. Start a timer
    started_at = start_timer(conn)
    assert started_at is not None

    # 2. Stop the timer
    entry1 = stop_timer(conn)
    assert entry1.id is not None
    assert entry1.duration_minutes >= 0

    # 3. Add a manual entry
    manual_entry = Entry(
        started_at="2025-01-15T09:00:00",
        ended_at="2025-01-15T12:30:00",
        duration_minutes=210,
        note="API design work",
    )
    entry2_id = add_entry(conn, manual_entry)
    assert entry2_id is not None

    # 4. Edit that entry
    assert update_entry(conn, entry2_id, hours=4.0, note="Updated API design")
    edited = get_entry(conn, entry2_id)
    assert edited.duration_minutes == 240  # 4 hours * 60
    assert edited.note == "Updated API design"

    # 5. Generate an invoice
    output_path = str(tmp_path / "invoices" / "test-invoice.pdf")
    invoice = generate_invoice(
        conn, settings, output_path=output_path, note="January work"
    )
    assert invoice.id is not None
    assert invoice.invoice_number == "INV-0001"
    assert invoice.total_amount > 0

    # 6. Verify the invoice PDF file exists on disk
    assert Path(output_path).exists()

    # 7. Verify the entries are marked as invoiced in the DB
    all_entries = get_entries(conn)
    assert len(all_entries) == 2
    for entry in all_entries:
        assert entry.invoiced is True
        assert entry.invoice_id == invoice.id
