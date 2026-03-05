"""Data models for TimeCard — dataclasses representing entries, invoices, and sessions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Entry:
    """A time tracking entry, either from a timer session or manual input.

    Args:
        id: Auto-incremented primary key.
        started_at: ISO 8601 timestamp when the work started.
        ended_at: ISO 8601 timestamp when the work ended (None if in progress).
        duration_minutes: Computed duration in minutes.
        note: Optional description of work performed.
        invoiced: Whether this entry has been included in an invoice.
        invoice_id: Foreign key to the invoice that includes this entry.
    """

    id: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_minutes: Optional[float] = None
    note: Optional[str] = None
    invoiced: bool = False
    invoice_id: Optional[int] = None

    def hours(self) -> float:
        """Return duration as hours, rounded to two decimal places."""
        if self.duration_minutes is None:
            return 0.0
        return round(self.duration_minutes / 60, 2)


@dataclass
class Invoice:
    """A generated invoice covering a set of time entries.

    Args:
        id: Auto-incremented primary key.
        invoice_number: Human-readable invoice number (e.g. INV-0042).
        period_start: ISO 8601 date for the start of the billing period.
        period_end: ISO 8601 date for the end of the billing period.
        total_hours: Sum of hours for all included entries.
        total_amount: total_hours * hourly rate.
        created_at: ISO 8601 timestamp when the invoice was created.
        pdf_path: Local filesystem path to the generated PDF.
        note: Optional project/work description.
    """

    id: Optional[int] = None
    invoice_number: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    total_hours: Optional[float] = None
    total_amount: Optional[float] = None
    created_at: Optional[str] = None
    pdf_path: Optional[str] = None
    note: Optional[str] = None


@dataclass
class ActiveSession:
    """Represents a currently running timer session.

    Args:
        id: Always 1 (only one active session allowed).
        started_at: ISO 8601 timestamp when the timer was started.
    """

    id: int = 1
    started_at: Optional[str] = None

    def elapsed_minutes(self) -> float:
        """Return minutes elapsed since the session started.

        Returns:
            Minutes elapsed, or 0.0 if started_at is not set.
        """
        if self.started_at is None:
            return 0.0
        start = datetime.fromisoformat(self.started_at)
        now = datetime.now(start.tzinfo)
        return (now - start).total_seconds() / 60
