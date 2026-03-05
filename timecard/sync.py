"""Google Sheets sync for TimeCard — pushes time entries to a configured spreadsheet."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from timecard.config import Settings
from timecard.db import get_entries

# Scopes required for reading/writing Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_DIR = Path.home() / ".timecard"
TOKEN_PATH = CREDENTIALS_DIR / "google_token.json"
CLIENT_SECRETS_PATH = CREDENTIALS_DIR / "client_secrets.json"


def authenticate() -> Credentials:
    """Run the Google OAuth flow and save credentials locally.

    Launches a local browser-based OAuth consent screen. The user grants
    Sheets access, and the resulting token is saved to ~/.timecard/google_token.json.

    Returns:
        Authorized Google OAuth2 Credentials.

    Raises:
        FileNotFoundError: If client_secrets.json is not found.
    """
    if not CLIENT_SECRETS_PATH.exists():
        raise FileNotFoundError(
            f"Google client secrets not found at {CLIENT_SECRETS_PATH}. "
            "Download your OAuth client JSON from the Google Cloud Console "
            "and save it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    return creds


def _load_credentials() -> Credentials:
    """Load saved Google OAuth credentials from disk.

    Returns:
        Authorized Credentials.

    Raises:
        FileNotFoundError: If no saved token exists (user needs to run auth first).
    """
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            "No Google credentials found. Run 'timecard auth' first."
        )

    creds_data = json.loads(TOKEN_PATH.read_text())
    return Credentials.from_authorized_user_info(creds_data, SCOPES)


def sync_to_sheets(
    conn: sqlite3.Connection,
    settings: Settings,
    credentials: Optional[Credentials] = None,
) -> int:
    """Push all time entries to the configured Google Sheet.

    Upserts entries by ID: if a row with the same entry ID already exists
    in the sheet, it is updated; otherwise a new row is appended.

    Args:
        conn: An open SQLite connection.
        settings: Application settings (must have google_sheet_id set).
        credentials: Optional pre-loaded credentials. If None, loads from disk.

    Returns:
        Number of entries synced.

    Raises:
        ValueError: If google_sheet_id is not configured.
        FileNotFoundError: If credentials are not available.
    """
    if not settings.google_sheet_id:
        raise ValueError(
            "Google Sheet ID not configured. Set GOOGLE_SHEET_ID in your .env file."
        )

    if credentials is None:
        credentials = _load_credentials()

    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(settings.google_sheet_id).sheet1

    entries = get_entries(conn)
    if not entries:
        return 0

    # Ensure header row exists
    expected_headers = ["ID", "Started At", "Ended At", "Duration (min)", "Note", "Invoiced", "Invoice ID"]
    try:
        existing_headers = sheet.row_values(1)
    except Exception:
        existing_headers = []

    if existing_headers != expected_headers:
        sheet.update(range_name="A1", values=[expected_headers])

    # Build a map of existing entry IDs to row numbers for upsert
    existing_ids: dict[str, int] = {}
    try:
        id_column = sheet.col_values(1)
        for row_num, cell_value in enumerate(id_column[1:], start=2):  # skip header
            if cell_value:
                existing_ids[str(cell_value)] = row_num
    except Exception:
        pass

    # Upsert each entry
    for entry in entries:
        row_data = [
            entry.id,
            entry.started_at or "",
            entry.ended_at or "",
            entry.duration_minutes or 0,
            entry.note or "",
            int(entry.invoiced),
            entry.invoice_id or "",
        ]

        entry_id_str = str(entry.id)
        if entry_id_str in existing_ids:
            row_num = existing_ids[entry_id_str]
            sheet.update(range_name=f"A{row_num}", values=[row_data])
        else:
            sheet.append_row(row_data)

    return len(entries)
