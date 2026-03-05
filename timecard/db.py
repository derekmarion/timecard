"""SQLite database layer for TimeCard — schema initialization and CRUD operations."""

import sqlite3
from pathlib import Path
from typing import Optional

from timecard.models import ActiveSession, Entry, Invoice


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection and ensure the schema exists.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist.

    Args:
        conn: An open SQLite connection.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            ended_at TEXT,
            duration_minutes REAL,
            note TEXT,
            invoiced INTEGER DEFAULT 0,
            invoice_id INTEGER,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            total_hours REAL NOT NULL,
            total_amount REAL NOT NULL,
            created_at TEXT NOT NULL,
            pdf_path TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS active_session (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            started_at TEXT NOT NULL
        );
        """
    )


# --- Entry CRUD ---


def add_entry(conn: sqlite3.Connection, entry: Entry) -> int:
    """Insert a new time entry.

    Args:
        conn: An open SQLite connection.
        entry: The Entry to insert (id is ignored).

    Returns:
        The auto-generated entry ID.
    """
    cur = conn.execute(
        """INSERT INTO entries (started_at, ended_at, duration_minutes, note, invoiced, invoice_id)
           VALUES (:started_at, :ended_at, :duration_minutes, :note, :invoiced, :invoice_id)""",
        {
            "started_at": entry.started_at,
            "ended_at": entry.ended_at,
            "duration_minutes": entry.duration_minutes,
            "note": entry.note,
            "invoiced": int(entry.invoiced),
            "invoice_id": entry.invoice_id,
        },
    )
    conn.commit()
    return cur.lastrowid


def get_entry(conn: sqlite3.Connection, entry_id: int) -> Optional[Entry]:
    """Fetch a single entry by ID.

    Args:
        conn: An open SQLite connection.
        entry_id: The entry's primary key.

    Returns:
        An Entry if found, else None.
    """
    row = conn.execute(
        "SELECT * FROM entries WHERE id = :id", {"id": entry_id}
    ).fetchone()
    if row is None:
        return None
    return _row_to_entry(row)


def get_entries(
    conn: sqlite3.Connection,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    invoiced: Optional[bool] = None,
) -> list[Entry]:
    """Fetch entries with optional filters.

    Args:
        conn: An open SQLite connection.
        start_date: If set, only return entries with started_at >= this date.
        end_date: If set, only return entries with started_at <= this date.
        invoiced: If set, filter by invoiced status.

    Returns:
        List of matching Entry objects ordered by started_at.
    """
    query = "SELECT * FROM entries WHERE 1=1"
    params: dict = {}

    if start_date:
        query += " AND started_at >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND started_at <= :end_date"
        params["end_date"] = end_date + "T23:59:59"
    if invoiced is not None:
        query += " AND invoiced = :invoiced"
        params["invoiced"] = int(invoiced)

    query += " ORDER BY started_at"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_entry(r) for r in rows]


def update_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    hours: Optional[float] = None,
    note: Optional[str] = None,
) -> bool:
    """Update an entry's hours and/or note.

    Args:
        conn: An open SQLite connection.
        entry_id: The entry's primary key.
        hours: If set, update duration_minutes to hours * 60.
        note: If set, update the note field.

    Returns:
        True if the entry was found and updated, False otherwise.
    """
    entry = get_entry(conn, entry_id)
    if entry is None:
        return False

    if hours is not None:
        conn.execute(
            "UPDATE entries SET duration_minutes = :minutes WHERE id = :id",
            {"minutes": hours * 60, "id": entry_id},
        )
    if note is not None:
        conn.execute(
            "UPDATE entries SET note = :note WHERE id = :id",
            {"note": note, "id": entry_id},
        )
    conn.commit()
    return True


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    """Delete an entry by ID.

    Args:
        conn: An open SQLite connection.
        entry_id: The entry's primary key.

    Returns:
        True if the entry existed and was deleted, False otherwise.
    """
    cur = conn.execute(
        "DELETE FROM entries WHERE id = :id", {"id": entry_id}
    )
    conn.commit()
    return cur.rowcount > 0


def mark_entries_invoiced(
    conn: sqlite3.Connection, entry_ids: list[int], invoice_id: int
) -> None:
    """Mark a list of entries as invoiced.

    Args:
        conn: An open SQLite connection.
        entry_ids: List of entry IDs to mark.
        invoice_id: The invoice ID to associate them with.
    """
    if not entry_ids:
        return
    for eid in entry_ids:
        conn.execute(
            "UPDATE entries SET invoiced = 1, invoice_id = :invoice_id WHERE id = :id",
            {"invoice_id": invoice_id, "id": eid},
        )
    conn.commit()


# --- Invoice CRUD ---


def add_invoice(conn: sqlite3.Connection, invoice: Invoice) -> int:
    """Insert a new invoice record.

    Args:
        conn: An open SQLite connection.
        invoice: The Invoice to insert (id is ignored).

    Returns:
        The auto-generated invoice ID.
    """
    cur = conn.execute(
        """INSERT INTO invoices (invoice_number, period_start, period_end, total_hours,
           total_amount, created_at, pdf_path, note)
           VALUES (:invoice_number, :period_start, :period_end, :total_hours,
                   :total_amount, :created_at, :pdf_path, :note)""",
        {
            "invoice_number": invoice.invoice_number,
            "period_start": invoice.period_start,
            "period_end": invoice.period_end,
            "total_hours": invoice.total_hours,
            "total_amount": invoice.total_amount,
            "created_at": invoice.created_at,
            "pdf_path": invoice.pdf_path,
            "note": invoice.note,
        },
    )
    conn.commit()
    return cur.lastrowid


def get_next_invoice_number(conn: sqlite3.Connection) -> str:
    """Generate the next sequential invoice number.

    Format: INV-NNNN (zero-padded to 4 digits).

    Args:
        conn: An open SQLite connection.

    Returns:
        The next invoice number string (e.g. "INV-0001").
    """
    row = conn.execute("SELECT MAX(id) as max_id FROM invoices").fetchone()
    next_num = (row["max_id"] or 0) + 1
    return f"INV-{next_num:04d}"


# --- Active Session CRUD ---


def get_active_session(conn: sqlite3.Connection) -> Optional[ActiveSession]:
    """Get the currently running timer session, if any.

    Args:
        conn: An open SQLite connection.

    Returns:
        An ActiveSession if a timer is running, else None.
    """
    row = conn.execute(
        "SELECT * FROM active_session WHERE id = :id", {"id": 1}
    ).fetchone()
    if row is None:
        return None
    return ActiveSession(id=row["id"], started_at=row["started_at"])


def start_session(conn: sqlite3.Connection, started_at: str) -> None:
    """Start a new timer session.

    Args:
        conn: An open SQLite connection.
        started_at: ISO 8601 timestamp for the session start.

    Raises:
        ValueError: If a session is already running.
    """
    if get_active_session(conn) is not None:
        raise ValueError("A timer session is already running.")
    conn.execute(
        "INSERT INTO active_session (id, started_at) VALUES (:id, :started_at)",
        {"id": 1, "started_at": started_at},
    )
    conn.commit()


def stop_session(conn: sqlite3.Connection) -> ActiveSession:
    """Stop the current timer session and remove it.

    Args:
        conn: An open SQLite connection.

    Returns:
        The ActiveSession that was stopped.

    Raises:
        ValueError: If no session is currently running.
    """
    session = get_active_session(conn)
    if session is None:
        raise ValueError("No timer session is currently running.")
    conn.execute("DELETE FROM active_session WHERE id = :id", {"id": 1})
    conn.commit()
    return session


def _row_to_entry(row: sqlite3.Row) -> Entry:
    """Convert a sqlite3.Row to an Entry dataclass.

    Args:
        row: A database row from the entries table.

    Returns:
        An Entry instance.
    """
    return Entry(
        id=row["id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        duration_minutes=row["duration_minutes"],
        note=row["note"],
        invoiced=bool(row["invoiced"]),
        invoice_id=row["invoice_id"],
    )
