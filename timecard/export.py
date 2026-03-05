"""CSV export for TimeCard — generates CSV from time entries."""

import csv
import io
import sqlite3
from typing import Optional

from timecard.db import get_entries


def export_entries_csv(
    conn: sqlite3.Connection,
    period: Optional[str] = None,
) -> str:
    """Export time entries as a CSV string.

    Args:
        conn: An open SQLite connection.
        period: Optional filter — 'week', 'biweekly', or 'month'.

    Returns:
        CSV string with header row and one row per entry.
    """
    start_date = None
    end_date = None
    if period:
        from timecard.invoice import _get_period_dates

        start_date, end_date = _get_period_dates(period)

    entries = get_entries(conn, start_date=start_date, end_date=end_date)

    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow(["ID", "Date", "Hours", "Note", "Invoiced"])
    for e in entries:
        writer.writerow([
            e.id,
            e.started_at[:10] if e.started_at else "",
            e.hours(),
            e.note or "",
            "Yes" if e.invoiced else "No",
        ])
    return f.getvalue()
