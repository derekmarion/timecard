"""Configuration management for TimeCard — loads settings from .env files and environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# XDG Base Directory defaults
DEFAULT_CONFIG_PATH = Path("~/.config/timecard/.env")
DEFAULT_DB_PATH = Path("~/.local/share/timecard/timecard.db")


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
                f"TIMECARD_DB_PATH resolves to a directory, not a file: {path}\n"
                "Set it to a file path, e.g. ~/.local/share/timecard/timecard.db"
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
                  TIMECARD_CONFIG_PATH env var or defaults to .env in cwd.

    Returns:
        A populated Settings instance.
    """
    if env_path is None:
        env_path = os.environ.get("TIMECARD_CONFIG_PATH")

    if env_path:
        load_dotenv(env_path)
    else:
        # Try XDG config location, then fall back to cwd .env
        xdg_config = DEFAULT_CONFIG_PATH.expanduser()
        if xdg_config.exists():
            load_dotenv(xdg_config)
        else:
            load_dotenv()

    return Settings(
        hourly_rate=float(os.environ.get("HOURLY_RATE", "150")),
        contractor_name=os.environ.get("CONTRACTOR_NAME", ""),
        contractor_address=os.environ.get("CONTRACTOR_ADDRESS", ""),
        contractor_email=os.environ.get("CONTRACTOR_EMAIL", ""),
        client_name=os.environ.get("CLIENT_NAME", ""),
        client_address=os.environ.get("CLIENT_ADDRESS", ""),
        invoice_output_dir=os.environ.get("INVOICE_OUTPUT_DIR", "~/invoices"),
        payment_instructions=os.environ.get(
            "PAYMENT_INSTRUCTIONS", "Please remit payment within 30 days."
        ),
        google_sheet_id=os.environ.get("GOOGLE_SHEET_ID") or None,
        db_path=os.environ.get("TIMECARD_DB_PATH", str(DEFAULT_DB_PATH)),
    )
