"""Timer logic for TimeCard — start, stop, and status operations."""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from timecard.db import add_entry, get_active_session, start_session, stop_session
from timecard.models import ActiveSession, Entry


def start_timer(conn: sqlite3.Connection) -> str:
    """Start a new timer session.

    Args:
        conn: An open SQLite connection.

    Returns:
        ISO 8601 timestamp of the session start.

    Raises:
        ValueError: If a timer is already running.
    """
    now = datetime.now(timezone.utc).isoformat()
    start_session(conn, now)
    return now


def stop_timer(conn: sqlite3.Connection) -> Entry:
    """Stop the current timer session and create a time entry.

    Calculates the duration between start and stop, inserts a completed
    entry into the database, and removes the active session.

    Args:
        conn: An open SQLite connection.

    Returns:
        The completed Entry with duration calculated.

    Raises:
        ValueError: If no timer is currently running.
    """
    session = stop_session(conn)
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(session.started_at)
    duration_minutes = (now - start).total_seconds() / 60

    entry = Entry(
        started_at=session.started_at,
        ended_at=now.isoformat(),
        duration_minutes=round(duration_minutes, 2),
    )
    entry_id = add_entry(conn, entry)
    entry.id = entry_id
    return entry


def get_timer_status(conn: sqlite3.Connection) -> Optional[dict]:
    """Check if a timer is running and how long it's been active.

    Args:
        conn: An open SQLite connection.

    Returns:
        A dict with 'running', 'started_at', and 'elapsed_minutes' keys
        if a timer is active, or a dict with 'running': False if not.
    """
    session = get_active_session(conn)
    if session is None:
        return {"running": False}

    elapsed = session.elapsed_minutes()
    return {
        "running": True,
        "started_at": session.started_at,
        "elapsed_minutes": round(elapsed, 2),
    }
