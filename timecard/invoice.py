"""Invoice generation for TimeCard — renders HTML templates to PDF using WeasyPrint."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from timecard.config import Settings
from timecard.db import (
    add_invoice,
    get_entries,
    get_next_invoice_number,
    mark_entries_invoiced,
)
from timecard.models import Entry, Invoice


def _format_date(date_str: str) -> str:
    """Format a YYYY-MM-DD date string as 'Mar 4, 2026' (no leading zero on day)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _get_period_dates(period: str) -> tuple[str, str]:
    """Calculate start and end dates for a calendar-aligned billing period.

    Periods use the last complete calendar-aligned window:
    - 'week': Last complete Mon–Sun week (the 7-day week ending on the
      most recent past Sunday).
    - 'biweekly': Last 2 complete weeks — 14 days ending on the most
      recent past Sunday.
    - 'month': Last complete calendar month. E.g. if today is March 4,
      the period is Feb 1–Feb 28/29.

    Args:
        period: One of 'biweekly', 'week', or 'month'.

    Returns:
        Tuple of (start_date, end_date) as ISO 8601 date strings.
    """
    today = datetime.now(timezone.utc).date()

    if period == "week":
        # Last complete Mon–Sun week.
        # isoweekday(): Mon=1 … Sun=7. Days since last Sunday:
        days_since_sunday = today.isoweekday() % 7  # Sun=0, Mon=1, …, Sat=6
        last_sunday = today - timedelta(days=days_since_sunday)
        end = last_sunday
        start = end - timedelta(days=6)  # Monday of that week
    elif period == "biweekly":
        # Last 2 complete weeks ending on the most recent past Sunday.
        days_since_sunday = today.isoweekday() % 7
        last_sunday = today - timedelta(days=days_since_sunday)
        end = last_sunday
        start = end - timedelta(days=13)  # Monday two weeks before
    elif period == "month":
        # Last complete calendar month. E.g. on March 4 → Feb 1 to Feb 28.
        first_of_this_month = today.replace(day=1)
        end = first_of_this_month - timedelta(days=1)  # last day of prev month
        start = end.replace(day=1)  # first day of prev month
    else:
        # Default: all time (use a far-past start date)
        start = datetime(2000, 1, 1).date()
        end = today

    return start.isoformat(), end.isoformat()


def generate_invoice(
    conn: sqlite3.Connection,
    settings: Settings,
    period: Optional[str] = None,
    output_path: Optional[str] = None,
    note: Optional[str] = None,
    number: Optional[int] = None,
) -> Invoice:
    """Generate a PDF invoice for uninvoiced entries.

    When period is specified ('week', 'biweekly', 'month'), only entries
    within that calendar-aligned window are included. When period is None,
    ALL uninvoiced entries are included regardless of date.

    Args:
        conn: An open SQLite connection.
        settings: Application settings with contractor/client info.
        period: Optional billing period — 'week', 'biweekly', or 'month'.
                If None, invoices all uninvoiced entries.
        output_path: Optional explicit path for the PDF. If None, auto-generates
                     a filename in the configured invoice output directory.
        note: Optional note to include on the invoice.
        number: Optional integer to use as the invoice number instead of the
                auto-incremented value. Formatted as INV-NNNN.

    Returns:
        The created Invoice record.

    Raises:
        ValueError: If there are no uninvoiced entries in the period.
    """
    if period is not None:
        period_start, period_end = _get_period_dates(period)
        entries = get_entries(
            conn, start_date=period_start, end_date=period_end, invoiced=False
        )
    else:
        entries = get_entries(conn, invoiced=False)
        # period_start/period_end are derived from the actual entries below,
        # after the empty-check guard.
    if not entries:
        if period is not None:
            raise ValueError(
                f"No uninvoiced entries found for period {period_start} to {period_end}."
            )
        raise ValueError("No uninvoiced entries found.")

    # When no period filter was used, derive the range from actual entries.
    if period is None:
        period_start = entries[0].started_at[:10]
        period_end = entries[-1].started_at[:10]

    total_hours = round(sum(e.hours() for e in entries), 2)
    total_amount = round(total_hours * settings.hourly_rate, 2)
    if number is not None:
        if number < 0:
            raise ValueError(f"Invoice number must be >= 0, got {number}")
        invoice_number = f"INV-{number:04d}"
        existing = conn.execute(
            "SELECT id FROM invoices WHERE invoice_number = :n", {"n": invoice_number}
        ).fetchone()
        if existing is not None:
            raise ValueError(f"Invoice number {invoice_number} already exists.")
    else:
        invoice_number = get_next_invoice_number(conn, settings.invoice_number_start)
    created_at = datetime.now(timezone.utc).isoformat()

    # Determine output path
    if output_path is None:
        out_dir = settings.get_invoice_output_dir()
        output_path = str(out_dir / f"{invoice_number}.pdf")
        if Path(output_path).exists():
            raise ValueError(f"Output file already exists: {output_path}")

    # Render HTML from template
    html_content = _render_invoice_html(
        entries=entries,
        invoice_number=invoice_number,
        period_start=period_start,
        period_end=period_end,
        total_hours=total_hours,
        total_amount=total_amount,
        hourly_rate=settings.hourly_rate,
        settings=settings,
        note=note,
    )

    # Generate PDF
    _write_pdf(html_content, output_path)

    # Save invoice record
    invoice = Invoice(
        invoice_number=invoice_number,
        period_start=period_start,
        period_end=period_end,
        total_hours=total_hours,
        total_amount=total_amount,
        created_at=created_at,
        pdf_path=output_path,
        note=note,
    )
    invoice_id = add_invoice(conn, invoice)
    invoice.id = invoice_id

    # Mark entries as invoiced
    entry_ids = [e.id for e in entries if e.id is not None]
    mark_entries_invoiced(conn, entry_ids, invoice_id)

    return invoice


def _render_invoice_html(
    entries: list[Entry],
    invoice_number: str,
    period_start: str,
    period_end: str,
    total_hours: float,
    total_amount: float,
    hourly_rate: float,
    settings: Settings,
    note: Optional[str] = None,
) -> str:
    """Render the invoice HTML template with Jinja2.

    Args:
        entries: List of time entries to include as line items.
        invoice_number: The invoice number string.
        period_start: Billing period start date.
        period_end: Billing period end date.
        total_hours: Sum of all entry hours.
        total_amount: Total dollar amount due.
        hourly_rate: Hourly billing rate.
        settings: Application settings for contractor/client info.
        note: Optional invoice note.

    Returns:
        Rendered HTML string.
    """
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("invoice.html")

    line_items = []
    for entry in entries:
        date_str = entry.started_at[:10] if entry.started_at else "N/A"
        line_items.append(
            {"date": _format_date(date_str) if date_str != "N/A" else date_str, "note": entry.note, "hours": entry.hours()}
        )

    return template.render(
        invoice_number=invoice_number,
        created_date=datetime.now(timezone.utc).strftime("%b %d, %Y"),
        period_start=_format_date(period_start),
        period_end=_format_date(period_end),
        contractor_name=settings.contractor_name,
        contractor_address=settings.contractor_address,
        contractor_email=settings.contractor_email,
        client_name=settings.client_name,
        client_address=settings.client_address,
        line_items=line_items,
        total_hours=total_hours,
        hourly_rate=hourly_rate,
        total_amount=total_amount,
        payment_instructions=settings.payment_instructions,
        note=note,
    )


def _write_pdf(html_content: str, output_path: str) -> None:
    """Write HTML content to a PDF file using WeasyPrint.

    Args:
        html_content: Rendered HTML string.
        output_path: Path where the PDF should be saved.
    """
    from weasyprint import HTML

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_content).write_pdf(output_path)
