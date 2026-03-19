"""Configuration management for TimeCard — loads settings from .env files and environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

# XDG Base Directory spec: respect XDG_CONFIG_HOME / XDG_DATA_HOME if set
DEFAULT_CONFIG_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")) / "timecard" / ".env"
)
DEFAULT_DB_PATH = (
    Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")) / "timecard" / "timecard.db"
)


@dataclass
class Settings:
    """Application settings loaded from environment variables.

    Args:
        hourly_rate: Billing rate per hour.
        contractor_name: Name of the contractor.
        contractor_address: Address of the contractor.
        contractor_email: Email of the contractor.
        client_name: Name of the client.
        client_address: Address of the client.
        invoice_output_dir: Directory to write generated PDFs.
        payment_instructions: Payment instructions included on invoices.
        google_sheet_id: Optional Google Sheet ID for sync.
        db_path: Path to the SQLite database file.
        invoice_number_start: Offset added to the sequential invoice counter.
                              Set via INVOICE_NUMBER_START for users migrating
                              from a prior invoicing system (e.g. 100 → first
                              invoice is INV-0101).
    """

    hourly_rate: float = 150.0
    contractor_name: str = ""
    contractor_address: str = ""
    contractor_email: str = ""
    client_name: str = ""
    client_address: str = ""
    invoice_output_dir: str = "~/invoices"
    payment_instructions: str = "Please remit payment within 30 days."
    google_sheet_id: Optional[str] = None
    db_path: str = str(DEFAULT_DB_PATH)
    invoice_number_start: int = 0

    def get_db_path(self) -> Path:
        """Return the resolved database path, creating parent directories if needed.

        Returns:
            Absolute Path to the SQLite database file.

        Raises:
            ValueError: If the resolved path is an existing directory.
        """
        path = Path(self.db_path).expanduser()
        if path.is_dir():
            raise ValueError(
                f"DB path resolves to a directory, not a file: {path}\n"
                "Set a file path via TIMECARD_DB_PATH or db_path in your .env file, "
                "e.g. ~/.local/share/timecard/timecard.db"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def get_invoice_output_dir(self) -> Path:
        """Return the resolved invoice output directory, creating it if needed.

        Returns:
            Absolute Path to the invoice output directory.
        """
        path = Path(self.invoice_output_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path


def load_settings(env_path: Optional[str] = None) -> Settings:
    """Load settings from a .env file and/or environment variables.

    Environment variables override .env file values. The config file path
    can be set via the TIMECARD_CONFIG_PATH env var.

    Args:
        env_path: Optional explicit path to .env file. If None, uses
                  TIMECARD_CONFIG_PATH env var, then XDG config location.

    Returns:
        A populated Settings instance.
    """
    if env_path is None:
        env_path = os.environ.get("TIMECARD_CONFIG_PATH")

    if env_path is None:
        xdg_config = DEFAULT_CONFIG_PATH.expanduser()
        if xdg_config.exists():
            env_path = str(xdg_config)

    # Read file values without modifying os.environ so env vars always win
    file_vals: dict[str, Optional[str]] = dotenv_values(env_path) if env_path else {}

    def _get(key: str, default: str = "") -> str:
        """Return env var if set (even if empty), else file value, else default."""
        if key in os.environ:
            return os.environ[key]
        val = file_vals.get(key)
        return val if val is not None else default

    return Settings(
        hourly_rate=float(_get("HOURLY_RATE", "150")),
        contractor_name=_get("CONTRACTOR_NAME"),
        contractor_address=_get("CONTRACTOR_ADDRESS"),
        contractor_email=_get("CONTRACTOR_EMAIL"),
        client_name=_get("CLIENT_NAME"),
        client_address=_get("CLIENT_ADDRESS"),
        invoice_output_dir=_get("INVOICE_OUTPUT_DIR", "~/invoices"),
        payment_instructions=_get(
            "PAYMENT_INSTRUCTIONS", "Please remit payment within 30 days."
        ),
        google_sheet_id=_get("GOOGLE_SHEET_ID") or None,
        db_path=_get("TIMECARD_DB_PATH", str(DEFAULT_DB_PATH)),
        invoice_number_start=int(_get("INVOICE_NUMBER_START", "0")),
    )
