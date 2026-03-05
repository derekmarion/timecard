"""CLI interface for TimeCard — all Typer commands wired together."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from timecard.config import load_settings
from timecard.db import (
    add_entry,
    delete_entry,
    get_connection,
    get_entries,
    get_entry,
    update_entry,
)
from timecard.models import Entry

app = typer.Typer(help="TimeCard — time tracking and invoicing for 1099 contractors.")


def _get_conn():
    """Get a database connection using current settings."""
    settings = load_settings()
    return get_connection(settings.get_db_path())


def _output(data: dict, as_json: bool) -> None:
    """Print output as JSON or human-readable text.

    Args:
        data: Dict to output.
        as_json: If True, print as JSON. Otherwise print key: value pairs.
    """
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        for key, value in data.items():
            typer.echo(f"{key}: {value}")


@app.command()
def start(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Start a timer session."""
    from timecard.timer import start_timer

    conn = _get_conn()
    try:
        started_at = start_timer(conn)
    except ValueError as e:
        _output({"error": str(e)}, json_output)
        raise typer.Exit(code=1)

    _output({"status": "started", "started_at": started_at}, json_output)


@app.command()
def stop(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Stop the current timer session and log the entry."""
    from timecard.timer import stop_timer

    conn = _get_conn()
    try:
        entry = stop_timer(conn)
    except ValueError as e:
        _output({"error": str(e)}, json_output)
        raise typer.Exit(code=1)

    _output(
        {
            "status": "stopped",
            "entry_id": entry.id,
            "duration_minutes": entry.duration_minutes,
            "hours": entry.hours(),
        },
        json_output,
    )


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show whether a timer is running and for how long."""
    from timecard.timer import get_timer_status

    conn = _get_conn()
    result = get_timer_status(conn)
    _output(result, json_output)


@app.command()
def add(
    date: str = typer.Option(..., help="Date of the entry (YYYY-MM-DD)"),
    hours: float = typer.Option(..., help="Number of hours worked"),
    note: Optional[str] = typer.Option(None, help="Description of work"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Manually add a time entry."""
    conn = _get_conn()

    started_at = f"{date}T00:00:00"
    entry = Entry(
        started_at=started_at,
        ended_at=f"{date}T{int(hours):02d}:00:00",
        duration_minutes=hours * 60,
        note=note,
    )
    entry_id = add_entry(conn, entry)

    _output(
        {"status": "added", "entry_id": entry_id, "date": date, "hours": hours},
        json_output,
    )


@app.command()
def log(
    period: Optional[str] = typer.Option(
        None, help="Filter period: week, biweekly, or month"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show a log of time entries."""
    conn = _get_conn()

    start_date = None
    end_date = None
    if period:
        from timecard.invoice import _get_period_dates

        start_date, end_date = _get_period_dates(period)

    entries = get_entries(conn, start_date=start_date, end_date=end_date)

    if json_output:
        data = [
            {
                "id": e.id,
                "date": e.started_at[:10] if e.started_at else None,
                "hours": e.hours(),
                "note": e.note,
                "invoiced": e.invoiced,
            }
            for e in entries
        ]
        typer.echo(json.dumps(data, indent=2))
    else:
        if not entries:
            typer.echo("No entries found.")
            return
        typer.echo(f"{'ID':<6}{'Date':<14}{'Hours':<10}{'Note':<30}{'Invoiced'}")
        typer.echo("-" * 70)
        for e in entries:
            date_str = e.started_at[:10] if e.started_at else "N/A"
            note_str = (e.note or "")[:28]
            inv_str = "Yes" if e.invoiced else "No"
            typer.echo(f"{e.id:<6}{date_str:<14}{e.hours():<10}{note_str:<30}{inv_str}")


@app.command()
def edit(
    entry_id: int = typer.Argument(help="Entry ID to edit"),
    hours: Optional[float] = typer.Option(None, help="New hours value"),
    note: Optional[str] = typer.Option(None, help="New note"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Edit an existing time entry."""
    conn = _get_conn()

    if hours is None and note is None:
        _output({"error": "Provide --hours and/or --note to update."}, json_output)
        raise typer.Exit(code=1)

    success = update_entry(conn, entry_id, hours=hours, note=note)
    if not success:
        _output({"error": f"Entry {entry_id} not found."}, json_output)
        raise typer.Exit(code=1)

    _output({"status": "updated", "entry_id": entry_id}, json_output)


@app.command()
def delete(
    entry_id: int = typer.Argument(help="Entry ID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Delete a time entry."""
    conn = _get_conn()

    entry = get_entry(conn, entry_id)
    if entry is None:
        _output({"error": f"Entry {entry_id} not found."}, json_output)
        raise typer.Exit(code=1)

    if not yes:
        confirm = typer.confirm(f"Delete entry {entry_id}?")
        if not confirm:
            _output({"status": "cancelled"}, json_output)
            raise typer.Exit(code=0)

    delete_entry(conn, entry_id)
    _output({"status": "deleted", "entry_id": entry_id}, json_output)


@app.command()
def export(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
    period: Optional[str] = typer.Option(None, help="Filter period: week, biweekly, or month"),
) -> None:
    """Export time entries to CSV."""
    from timecard.export import export_entries_csv

    conn = _get_conn()
    csv_text = export_entries_csv(conn, period=period)

    if output:
        with open(output, "w", newline="") as f:
            f.write(csv_text)
        typer.echo(f"Exported entries to {output}")
    else:
        typer.echo(csv_text, nl=False)


@app.command()
def invoice(
    period: Optional[str] = typer.Option(
        None, help="Billing period: week, biweekly, or month"
    ),
    output: Optional[str] = typer.Option(None, help="Output path for the PDF"),
    note: Optional[str] = typer.Option(None, help="Invoice note"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Generate a PDF invoice for uninvoiced entries."""
    from timecard.invoice import generate_invoice

    conn = _get_conn()
    settings = load_settings()

    try:
        inv = generate_invoice(
            conn, settings, period=period, output_path=output, note=note
        )
    except ValueError as e:
        _output({"error": str(e)}, json_output)
        raise typer.Exit(code=1)

    _output(
        {
            "status": "generated",
            "invoice_number": inv.invoice_number,
            "total_hours": inv.total_hours,
            "total_amount": inv.total_amount,
            "pdf_path": inv.pdf_path,
        },
        json_output,
    )


@app.command()
def sync(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Sync time entries to Google Sheets."""
    from timecard.sync import sync_to_sheets

    conn = _get_conn()
    settings = load_settings()

    try:
        count = sync_to_sheets(conn, settings)
    except (ValueError, FileNotFoundError) as e:
        _output({"error": str(e)}, json_output)
        raise typer.Exit(code=2)

    _output({"status": "synced", "entries_synced": count}, json_output)


@app.command()
def auth(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Run Google OAuth flow to authorize Sheets access."""
    from timecard.sync import authenticate

    try:
        authenticate()
    except FileNotFoundError as e:
        _output({"error": str(e)}, json_output)
        raise typer.Exit(code=2)

    _output({"status": "authenticated"}, json_output)


@app.command()
def mcp() -> None:
    """Start the MCP server for agent integration."""
    from timecard.mcp_server import run_server

    run_server()
