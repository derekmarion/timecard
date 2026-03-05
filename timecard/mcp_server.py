"""MCP server for TimeCard — exposes time tracking tools for AI agent integration.

This is a thin wrapper over the existing business logic modules. No
business logic is duplicated here.
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from timecard.config import load_settings
from timecard.db import (
    add_entry,
    delete_entry,
    get_connection,
    get_entries,
    update_entry,
)
from timecard.models import Entry

mcp = FastMCP("TimeCard")


def _get_conn():
    """Get a database connection using current settings."""
    settings = load_settings()
    return get_connection(settings.get_db_path())


@mcp.tool()
def start_timer() -> dict:
    """Start a timer session. Errors if a session is already running.

    Returns:
        Dict with 'status' and 'started_at' keys.
    """
    from timecard.timer import start_timer as _start

    conn = _get_conn()
    started_at = _start(conn)
    return {"status": "started", "started_at": started_at}


@mcp.tool()
def stop_timer() -> dict:
    """Stop the current timer session and log the time entry.

    Returns:
        Dict with entry details including id, duration, and hours.
    """
    from timecard.timer import stop_timer as _stop

    conn = _get_conn()
    entry = _stop(conn)
    return {
        "status": "stopped",
        "entry_id": entry.id,
        "duration_minutes": entry.duration_minutes,
        "hours": entry.hours(),
    }


@mcp.tool()
def get_status() -> dict:
    """Check if a timer is currently running and for how long.

    Returns:
        Dict with 'running' boolean and optional 'started_at' and 'elapsed_minutes'.
    """
    from timecard.timer import get_timer_status

    conn = _get_conn()
    return get_timer_status(conn)


@mcp.tool()
def add_entry_tool(date: str, hours: float, note: Optional[str] = None) -> dict:
    """Manually log a time entry.

    Args:
        date: Date of the work (YYYY-MM-DD format).
        hours: Number of hours worked.
        note: Optional description of work performed.

    Returns:
        Dict with 'status' and 'entry_id'.
    """
    conn = _get_conn()
    entry = Entry(
        started_at=f"{date}T00:00:00",
        ended_at=f"{date}T{int(hours):02d}:00:00",
        duration_minutes=hours * 60,
        note=note,
    )
    entry_id = add_entry(conn, entry)
    return {"status": "added", "entry_id": entry_id}


@mcp.tool()
def get_log(period: Optional[str] = None) -> list[dict]:
    """Return time entries as a list of dicts.

    Args:
        period: Optional filter — 'week', 'biweekly', or 'month'.

    Returns:
        List of entry dicts with id, date, hours, note, and invoiced fields.
    """
    conn = _get_conn()

    start_date = None
    end_date = None
    if period:
        from timecard.invoice import _get_period_dates

        start_date, end_date = _get_period_dates(period)

    entries = get_entries(conn, start_date=start_date, end_date=end_date)
    return [
        {
            "id": e.id,
            "date": e.started_at[:10] if e.started_at else None,
            "hours": e.hours(),
            "note": e.note,
            "invoiced": e.invoiced,
        }
        for e in entries
    ]


@mcp.tool()
def edit_entry(id: int, hours: Optional[float] = None, note: Optional[str] = None) -> dict:
    """Update an existing time entry's hours and/or note.

    Args:
        id: The entry ID to edit.
        hours: New hours value (optional).
        note: New note text (optional).

    Returns:
        Dict with 'status' and 'entry_id'.
    """
    conn = _get_conn()
    success = update_entry(conn, id, hours=hours, note=note)
    if not success:
        return {"error": f"Entry {id} not found."}
    return {"status": "updated", "entry_id": id}


@mcp.tool()
def delete_entry_tool(id: int) -> dict:
    """Delete a time entry by ID.

    Args:
        id: The entry ID to delete.

    Returns:
        Dict with 'status' and 'entry_id'.
    """
    conn = _get_conn()
    success = delete_entry(conn, id)
    if not success:
        return {"error": f"Entry {id} not found."}
    return {"status": "deleted", "entry_id": id}


@mcp.tool()
def generate_invoice(
    period: Optional[str] = None, note: Optional[str] = None
) -> dict:
    """Generate a PDF invoice for uninvoiced time entries.

    Args:
        period: Optional billing period — 'week', 'biweekly', or 'month'.
                If omitted, invoices all uninvoiced entries.
        note: Optional note to include on the invoice.

    Returns:
        Dict with invoice details.
    """
    from timecard.invoice import generate_invoice as _generate

    conn = _get_conn()
    settings = load_settings()
    inv = _generate(conn, settings, period=period, note=note)
    return {
        "status": "generated",
        "invoice_number": inv.invoice_number,
        "total_hours": inv.total_hours,
        "total_amount": inv.total_amount,
        "pdf_path": inv.pdf_path,
    }


@mcp.tool()
def sync_to_sheets() -> dict:
    """Push all time entries to the configured Google Sheet.

    Returns:
        Dict with 'status' and 'entries_synced' count.
    """
    from timecard.sync import sync_to_sheets as _sync

    conn = _get_conn()
    settings = load_settings()
    count = _sync(conn, settings)
    return {"status": "synced", "entries_synced": count}


def run_server() -> None:
    """Start the MCP server on stdio transport."""
    mcp.run(transport="stdio")
